#!/usr/bin/env python3
"""
Générateur du classement repêchage NHL 2026 — modèle NORTHSTAR (Star Probability).
Évaluation joueur-par-joueur à partir des rapports de scouting.
"""

import csv
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from northstar_scoring import (
    NORTHSTAR_LABELS,
    NORTHSTAR_WEIGHTS,
    northstar_generate,
    northstar_overall,
)
from eligibility import is_draft_eligible_2026, parse_dob

from draft_config import DEFAULT_DRAFT_YEAR, paths_for_year

BASE = Path(__file__).parent
DRAFT_YEAR = DEFAULT_DRAFT_YEAR
_paths = paths_for_year(DRAFT_YEAR)
OUT_DOCS = _paths["analyses"]
OUT_CSV = _paths["csv"]
OUT_JSON = _paths["rankings"]
ELIGIBLE_TSV = _paths["eligible_tsv"]

# --- CONSENSUS (référence uniquement, ne détermine PAS le rang APEX) ---
CONSENSUS_RANKS = {
    "Gavin McKenna": 1,
    "Ivar Stenberg": 2,
    "Chase Reid": 3,
    "Caleb Malhotra": 4,
    "Keaton Verhoeff": 4,
    "Carson Carels": 6,
    "Viggo Björck": 7,
    "Viggo Bjorck": 7,
    "Alberts Smits": 8,
    "Alberts Šmits": 8,
    "Daxon Rudolph": 9,
    "Wyatt Cullen": 10,
    "Tynan Lawrence": 11,
    "Ryan Lin": 12,
    "Alexander Command": 13,
    "Ethan Belchetz": 14,
    "Malte Gustafsson": 15,
    "Liam Ruck": 16,
    "Oscar Hemming": 17,
    "Adam Novotný": 18,
    "Adam Novotony": 18,
    "Nikita Klepov": 19,
    "Elton Hermansson": 20,
    "J.P. Hurlbert": 21,
    "Mathis Preston": 22,
    "Ilia Morozov": 23,
    "Markus Ruck": 24,
    "Egor Shilov": 25,
    "Yegor Shilov": 25,
    "Oliver Suvanto": 26,
    "Tommy Bleyl": 27,
    "Maddox Dagenais": 28,
    "Xavier Villeneuve": 29,
    "Ryan Roobroeck": 30,
    "Jack Hextall": 31,
    "Nikita Shcherbakov": 32,
    "Juho Piiparinen": 33,
    "Adam Goljer": 34,
    "Casey Mutryn": 35,
    "Niklas Aaram-Olsen": 36,
    "Ethan Belchetz": 14,
    "William Håkansson": 38,
    "William Hakansson": 38,
    "Adam Valentini": 39,
    "Brooks Rogowski": 41,
    "Tomas Chrenko": 42,
    "Chrenko. Tomas": 42,
    "Chrenko Tomas": 42,
    "Marcus Nordmark": 44,
    "Tobias Trejbal": 45,
    "Gleb Pugachyov": 47,
    "Giorgos Pantelas": 49,
    "Chase Harrington": 50,
    "Victor Plante": 51,
    "Samu Alalauri": 53,
    "Oscar Holmertz": 55,
    "Matias Vanhanen": 56,
    "Alexander Bilecki": 58,
    "Adam Andersson": 59,
    "Axel Elofsson": 60,
    "Charlie Morrison": 61,
    "Brek Liske": 63,
    "Lars Steiner": 65,
    "Lavr Gashilov": 66,
    "Vladimir Dravecky": 67,
    "Vladimír Dravecký": 67,
    "Luke Schairer": 68,
    "Adam Nemec": 69,
    "Mikey Berchild": 71,
    "Alessandro Di Iorio": 72,
    "Nils Bartholdsson": 73,
    "Pierce Mbuyi": 74,
    "Braidy Wassilyn": 80,
    "Brady Wassilyn": 80,
    "Olivers Murnieks": 81,
    "Olivers Mūrnieks": 81,
    "Landon Nycz": 82,
    "Rudolfs Berzkalns": 84,
    "Rūdolfs Bērzkalns": 84,
    "Vertti Svensk": 86,
    "Colin Fitzgerald": 87,
    "Alan Shaikhlislamov": 88,
    "Harrison Boettiger": 90,
    "Luke Schairer": 68,
    "Beckham Edwards": 96,
    "Tyus Sparks": 98,
    "Vilho Vanhatalo": 99,
    "Beckett Hamilton": 100,
    "Reese Hamilton": 100,
    "Joe Iginla": 185,
    "Filip Růžička": 52,
    "Filip Ruzicka": 52,
    "Noa Taamu": 120,
    "Noa Ta'amu": 120,
    "Andrew Neill": 145,
    "Andrew O'Neill": 145,
    "Jonathan Prud": 160,
    "Jonathan Prud'homme": 160,
    "Frantisek Poletin": 95,
    "William Lacelle": 130,
    "Cole Bumgarner": 110,
    "Mans Josbrant": 115,
    "Daniil Skvortsov": 105,
    "Rio Kaiser": 108,
    "Carl Otto Magnusson": 112,
    "Zachary Wilson": 118,
    "Asanali Sarkenov": 125,
    "Artyom Vilchinsky": 128,
    "German Suzdorf": 122,
    "Eduard Bondar": 135,
    "Mikhail Katin": 140,
    "Nikita Ovcharov": 132,
    "Kadon McCann": 127,
    "Kolten Bridgeman": 124,
    "Dawson Gerwing": 126,
    "Mason Kraft": 133,
    "Parker Von Richter": 129,
    "Oliver Turner": 131,
    "Albin Laksonen": 134,
    "Caden Taylor": 136,
    "Joshua Avery": 138,
    "Lucas Karmiris": 142,
    "Jasper Kuhta": 144,
    "Lev Katzin": 155,
    "Bruno Osmanis": 148,
    "Jamiro Reber": 150,
    "Hugo Orrsten": 152,
    "Leo Sundqvist": 154,
    "Matej Mikes": 146,
    "David Krcal": 147,
    "Robin Antenen": 149,
    "Matej Pekar": 156,
    "Connor Davis": 158,
    "Liam Kilfoil": 159,
    "Michael Dec": 162,
    "Owen Conrad": 125,
    "Onni Kalto": 137,
    "Luka Radivojevic": 141,
    "Mike Aeschlimann": 143,
    "Gavin Garland": 151,
    "Joshua Glavin": 153,
    "Jacob Crawford": 157,
    "Matus Lisy": 161,
    "Ethan MacKenzie": 76,
    "Nic Whitehead": 163,
    "Bogdan Pestretsov": 164,
    "Xander Velliaris": 165,
    "Ruslan Karimov": 166,
    "Owen Schoettler": 167,
    "Arvid Johansson": 168,
    "Jonathan Brown": 169,
    "Andrei Zavadsky": 170,
    "Yuri Rummo": 171,
    "Nolen Geerdes": 172,
    "Hayden Barch": 173,
    "Arttu Välilä": 174,
    "Noah Jenken": 175,
    "Andrei Kuryanov": 176,
    "Jordan Gavin": 177,
    "Elliot Dube": 178,
    "PJ Fagan": 179,
    "Patrik Rusznyak": 180,
    "Alvar Ervasti": 181,
    "Alexandre Carbonneau": 182,
    "Lukas Sawchyn": 183,
    "Hugo Hallin": 184,
    "Filip Holst Persson": 186,
    "Noah Degenstein": 187,
    "Aapo Vanninen": 188,
    "Andreas Straka": 189,
    "Alonso Gosselin": 190,
    "Jonas Woo": 191,
    "Oliwer Sjöström": 192,
    "Sawyer Mayes": 193,
    "Derek Thurston": 194,
    "Drew Allison": 195,
    "Cameron Aucoin": 196,
    "Vladislav Ukhmylov": 197,
    "Vit Macek": 198,
    "Dryden Allen": 199,
    "Donato Bracco": 200,
}

RAW_PLAYERS = """
McKenna, Gavin	LW	6'0	165	L	CDN
Stenberg, Ivar	LW	5'11	170	L	SWE
Verhoeff, Keaton	D	6'4	212	R	CDN
Lawrence, Tynan	C	6'0	168	L	CDN
Cullen, Wyatt	C	6'1	180	L	USA
Rudolph, Daxon	D	6'1	194	R	CDN
Preston, Mathis	RW	5'11	168	R	CDN
Puchner, Luke	LW	5'10	183	L	USA	2008-01-02
Reid, Chase	D	6'2	185	R	USA
Lin, Ryan	D	5'11	174	R	CDN
Roobroeck, Ryan	C	6'4	190	L	CDN
Novotony, Adam	LW	6'1	198	L	CZE
Björck, Viggo	RW	5'9	165	R	SWE
Belchetz, Ethan	LW	6'5	227	L	CDN
Smits, Alberts	D	6'3	205	L	LAT
Villeneuve, Xavier	D	5'10	150	L	CDN
Ruck, Liam	RW	5'11	176	R	CDN
Tomik, Tobias	C	6'1	190	L	SVK
Hextall, Jack	C	6'0	183	R	USA
Steiner, Lars	RW	5'11	181	R	SUI
Edwards, Beckham	C	6'1	170	L	CDN
Shilov, Yegor	C	6'1	163	L	RUS
Berchild, Mikey	LW	5'9	172	L	USA
Suvanto, Oliver	C	6'3	209	L	FIN
Harrington, Chase	LW	6'0	196	L	CDN
Klepov, Nikita	LW	6'0	181	L	USA
Command, Alexander	C	6'0	179	L	SWE
Fitzgerald, Colin	C	6'2	194	R	CDN
Valentini, Adam	C	5'9	183	L	USA
Kosick, Noah	C	5'10	150	L	CDN
Di Iorio, Alessandro	RW	6'1	176	R	CDN
Nordmark, Marcus	RW	6'1	183	L	SWE
Morozov, Ilia	LW	6'3	196	L	RUS
Wassilyn, Braidy	LW	5'11	194	L	CDN
Hemming, Oscar	LW	6'3	187	L	FIN
Vlasov, Alexei	LW	5'9	161	R	RUS
Carels, Carson	D	6'1	174	L	CDN
Fyodorov, Viktor	C	5'10	176	L	RUS
Vanhatalo, Vilho	LW	6'3	187	L	FIN
Jardine, Evan	LW	6'0	179	L	USA
Bleyl, Tommy	D	6'0	161	R	CDN
Hermansson, Elton	RW	6'1	176	R	SWE
Rogowski, Brooks	C	6'6	214	R	CDN
Gashilov, Lavr	C	6'2	170	R	RUS
Shaikhlislamov, Alan	LW	6'0	174	L	RUS
Aaram-Olsen, Niklas	LW	6'1	179	L	SWE
Mbuyi, Pierce	LW	5'10	154	L	CDN
Zielinski, Blake	LW	6'0	174	L	USA
Melnikov, Yan	LW	5'10	176	R	KAZ
Veilleux, Philippe	LW	5'9	165	L	CDN
Murnieks, Olivers	C	6'1	194	L	LAT
Nycz, Landon	D	6'2	201	L	USA
Pugachyov, Gleb	LW	6'3	198	L	CDN
Hurlbert, J.P	RW	6'0	182	R	USA
Piiparinen, Juho	D	6'2	203	R	FIN
Pantelas, Giorgos	D	6'2	190	R	CDN
Sparks, Tyus	RW	6'0	196	L	USA
Schairer, Luke	D	6'2	187	R	USA
Plante, Victor	LW	5'9	148	L	USA
Shcherbakov, Nikita	C	6'0	172	L	RUS
Malhotra, Caleb	C	6'0	154	L	CDN
Korneyev, Kornei	RW	6'0	172	R	KAZ
Mutryn, Casey	RW	6'2	190	R	USA
Andersson, Adam	C	6'4	205	R	SWE
Ovcharov, Nikita	LW	6'2	196	R	RUS
Katin, Mikhail	D	6'4	205	R	RUS
Chudzinski, Rian	RW	6'1	190	L	USA
Taamu, Noa	D	6'2	238	R	USA
Singh, Rylan	D	5'11	187	R	CDN
Varga, Kalder	RW	5'11	170	R	CDN
Ilyin, Arseni	LW	6'2	181	L	RUS
Klimpke, Brayden	D	6'0	168	R	CAN
Dravecky, Vladimir	D	5'11	185	R	CZE
Gustafsson, Malte	D	6'4	190	L	SWE
Zurawski, Cole	RW	6'0	181	R	CDN
Hamilton, Reese	D	6'1	170	L	CDN
Capos, Michal	D	6'5	216	L	SVK
Iginla, Joe	RW	5'10	165		CDN
Růžička, Filip	G	6'7	230	R	CZE
Lajoie, Jett	C	5'11	179	L	CAN
Cloutier, Rafael	C	6'3	198	R	CAN
Karmanov, Alexander	D	NA	NA	L	RUS
Egan, Jimmy	C	6'2	185	R	USA
Lecompte, Nathan	C	5'10	165	L	CAN
Kuhta, Jasper	C	6'2	194	R	FIN
Fuder, Jaxon	LW	6'0	175	R	CAN
Karmiris, Lucas	C	5'11	190	L	CAN
Avery, Joshua	C	6'1	170	R	CAN
Taylor, Caden	LW	6'3	205	R	CAN
Katzin, Lev	C	5'8	176	R	CAN
Skvortsov, Daniil	D	6'4	214	R	RUS
Pobezal, Tomas	C	5'10	179	R	SVK
Osmanis, Bruno	RW	5'11	170	L	LAT
Reber, Jamiro	C	5'10	181	R	SUI
Temple, Cole	LW	5'10	163	R	CAN
Sundqvist, Leo	RW	5'9	170	L	SWE
Orrsten, Hugo	C	6'3	198	R	SWE
Beamish, Liam	C	5'11	190	R	CAN
Desjardins, Vincent	C	5'11	172	L	CAN
Nykyri, Niklas	D	6'2	190	R	FIN
Hynninen, Topias	C	5'11	176	R	FIN
Kraft, Mason	LW	5'11	190	R	USA
Svec, Martin	C	5'10	174	R	CZE
Krcal, David	LW	6'2	212	R	CZE
Antenen, Robin	LW	6'2	194	R	SUI
Vanhanen, Matias	C	5'10	170	R	FIN
Pekar, Matej	C	5'10	168	R	CZE
Davis, Connor	RW	6'1	174	L	CAN
Kilfoil, Liam	C	5'11	183	R	CAN
Somervuori, Jere	LW	6'0	159	R	SWE
Rhéaume-Mullen, Dakoda	D	6'0	181	R	USA
Andersen, Poul	C	6'1	181	L	USA
Mikes, Matej	C	6'3	205	L	CZE
Brisson, Nathan	LW	5'11	179	R	CAN
Dec, Michael	C	5'9	152	R	CAN
Fomin, Makar	D	5'11	165	R	RUS
Kapageridis, Jonathan	D	6'0	176	R	CAN
Wahlund, Joe	D	6'1	190	R	SWE
Delisle, Tristan	C	5'11	184	R	CAN
Conrad, Owen	D	6'3	209	R	CAN
Sinivuori, Lauri	LW	6'1	179	R	FIN
Lam, Tanner	RW	5'10	157	L	CAN
Mundy, Jeremiah	LW	6'3	201	R	SUI
Pennerborn, Viktor	D	6'1	190	L	SWE
Kalto, Onni	LW	6'2	192	R	FIN
Radivojevic, Luka	D	5'10	168	L	USA
Aeschlimann, Mike	C	6'2	183	L	SUI
Garland, Gavin	C	5'9	186	L	USA
Zaitsev, Maxim	LW	6'1	161	R	RUS
Glavin, Joshua	D	6'2	201	R	CAN
Crawford, Jacob	C	6'3	181	R	CAN
Lisy, Matus	D	6'1	181	R	SVK
MacKenzie, Ethan	D	6'0	174	R	CAN
Ruotsalainen, Veeti	D	5'11	165	R	FIN
Orpana, Eetu	C	6'1	196	R	FIN
Tomko, William	C	6'0	190	L	USA
Klaers, Danny	C	5'11	179	L	USA
Mensonen, Jasu	C	5'11	183	R	FIN
Morin, Zachary	LW	6'2	181	R	CAN
Groulx, Olivier	LW	6'1	187	R	CAN
Poltavchuk, Nikita	D	5'11	161	R	RUS
Sykora, Nicolas	C	6'0	174	R	USA
Petrenko, Daniil	LW	5'10	179	R	RUS
Gamzakov, Mikhail	D	5'11	165	R	RUS
Houle, Florent	RW	6'0	195	L	CAN
Vahalahti, Eetu	D	6'1	163	R	FIN
Weber, Ethan	D	6'0	190	L	USA
Skok, Jan	D	6'0	203	R	CZE
Fomin, Ivan	LW	5'8	137	R	RUS
Whitehead, Nic	C	5'10	167	R	USA
Suzdorf, German	C	6'7	209	R	RUS
Pestretsov, Bogdan	D	6'3	203	R	RUS
Velliaris, Xander	D	6'3	205	R	CAN
Karimov, Ruslan	RW	6'0	201	R	RUS
Schoettler, Owen	C	6'0	185	L	CAN
Johansson, Arvid	D	6'6	220	R	SWE
Viita, Frans	C	5'9	157	L	FIN
Brown, Jonathan	D	6'2	201	L	GER
Bondar, Eduard	D	6'5	194	L	RUS
Zavadsky, Andrei	D	5'9	137	R	RUS
Prud, Jonathan	D	5'10	168	R	CAN
Cameron, Carson	D	6'2	194	L	CAN
Malinek, Tomas	D	6'1	176	R	CZE
Ronald, Dylan	D	5'11	180	R	CAN
Rummo, Yuri	C	6'4	198	R	BLR
Geerdes, Nolen	D	6'0	183	R	USA
Barch, Hayden	D	6'0	181	L	USA
Välilä, Arttu	D	5'9	168	R	FIN
Jenken, Noah	D	6'3	190	R	CAN
Kuryanov, Andrei	C	5'9	157	R	RUS
Gavin, Jordan	D	5'11	187	R	CAN
Dube, Elliot	C	6'1	173	R	CAN
Fagan, PJ	C	6'1	205	R	CAN
Rusznyak, Patrik	D	6'4	203	L	SVK
Ervasti, Alvar	D	6'4	194	R	FIN
Carbonneau, Alexandre	D	6'4	205	R	CAN
Sawchyn, Lukas	RW	5'10	174	L	CAN
Hallin, Hugo	D	5'9	165	R	SWE
Persson, Filip Holst	RW	6'0	161	R	SWE
Degenstein, Noah	C	6'4	210	R	CAN
Vanninen, Aapo	C	6'0	176	R	FIN
Straka, Andreas	LW	6'0	188	R	SVK
Gosselin, Alonso	C	6'0	195	R	CAN
Woo, Jonas	D	5'9	165	L	CAN
Sjöström, Oliwer	D	6'0	173	R	SWE
Mayes, Sawyer	C	6'4	200	R	CAN
Vilchinsky, Artyom	D	6'4	243	R	RUS
Thurston, Derek	D	6'1	190	R	CAN
Allison, Drew	D	6'2	192	R	CAN
Sarkenov, Asanali	RW	6'4	203	R	KAZ
Aucoin, Cameron	D	6'1	190	R	USA
Ukhmylov, Vladislav	D	6'4	163	R	RUS
Macek, Vit	LW	6'2	174	R	CZE
Allen, Dryden	D	6'1	187	R	CAN
Bracco, Donato	D	5'10	161	R	USA
Gerwing, Dawson	C	6'4	231	R	CAN
Schmidt, Connor	LW	5'11	179	L	CAN
Cowan, Bobby	C	5'11	175	L	USA
Richter, Parker Von	D	6'1	194	L	CAN
Turner, Oliver	D	6'5	205	L	CAN
Labre, Maddox	D	6'2	179	R	CAN
Saari, Julius	D	6'2	187	R	FIN
Kotajarvi, Jesper	D	5'11	157	R	FIN
Bridgeman, Kolten	D	6'4	216	L	CAN
McCann, Kadon	C	6'3	205	R	CAN
Carrier, Shawn	C	5'10	181	R	CAN
Snelgrove, Parker	C	6'0	190	R	CAN
Laksonen, Albin	LW	6'4	209	L	SWE
Young, Aiden	LW	5'10	181	R	CAN
Virk, Savin	C	6'0	172	L	CAN
McGregor, Josh	D	6'3	174	R	CAN
Cullen, Brooks	C	6'0	185	R	USA
Matthews, Caleb	C	6'1	170	L	CAN
Baumuller, Joby	RW	5'11	185	L	CAN
Misiak, Alex	LW	6'0	183	R	SVK
Obobaifo, Aaron	C	5'10	185	R	CAN
Arrowsmith, Blake	C	6'0	190	L	USA
Koch, Cash	LW	6'0	196	R	CAN
Zalesak, Alex	RW	6'0	183	R	SVK
Kaiser, Rio	D	6'7	201	R	GER
Wilson, Zachary	D	6'6	187	R	CAN
Magnusson, Carl Otto	D	6'7	223	R	SWE
Neill, Andrew	C	6'2	194	L	USA
Chrenko, Tomas	C	5'10	170	R	SVK
Holmertz, Oscar	C	6'0	183	L	SWE
Nemec, Adam	LW	6'0	163	L	SVK
Katolicky, Simon	LW	6'4	187	L	CDN
Kolarik, Leon	LW	5'11	170	L	AUT
Amidovski, Nathan	C	6'2	170	L	CDN
Bilecki, Alexander	D	6'1	154	L	CDN
Carey, Rider	C	6'0	176	R	CDN
Challenger, Tyler	LW	6'2	198	L	CDN
Flugins, Karlis	RW	5'11	185	R	LAT
Frasca, Nick	D	6'1	185	L	CDN
Galiyanov, Ivan	LW	5'10	174	L	CDN
Hawery, Logan	LW	5'10	170	L	CDN
Hicks, Carter	D	6'1	165	R	CDN
Lemieux, Jean-Cristoph	C	5'11	176	L	CDN
McLean, Alex	LW	5'10	174	L	CDN
O'Donnell, Aiden	LW	6'1	172	L	CDN
Royston, Wesley	RW	6'3	174	R	CDN
Stevens, Carter	D	6'1	183	R	CDN
Varosyan, Raflik	LW	6'0	179	L	RUS
Vaughn, Parker	RW	6'1	190	R	CDN
Wassilyn, Brady	LW	5'11	194	L	CDN
Bélanger, Louis-Francois	LW	5'8	163	L	CDN
Bent, Will	RW	6'1	196	R	CDN
Chartrand, Cameron	D	6'1	205	R	CDN
Cossette-Ayotte, Benjamin	D	6'1	172	R	CDN
Dagenais, Maddox	C	6'2	181	L	CDN
Doyle, Eddie	D	6'3	179	L	CDN
Lacelle, William	G	6'0	168	L	CDN
L'Italien, Romain	C	6'1	181	R	CDN
Lygitsakos, Chad	C	5'8	170	L	CDN
McKinnon, Noah	D	5'9	174	R	CDN
Morrison, Charlie	D	6'3	185	L	CDN
Plouffe, Jayden	LW	5'11	179	L	CDN
Ricard, Emile	LW	6'0	172	L	CDN
Rousseau, Tomas	RW	5'10	165	R	CDN
Rozzi, Dylan	LW	5'11	152	L	CDN
Yared, William	C	6'2	190	R	CDN
Boychuk, Riley	RW	5'9	161	R	CDN
Edmonstone, Logan	G	5'11	170	L	CDN
Joudrey, Caelen	F	6'4	172	R	CDN
Liske, Brek	D	6'1	187	R	CDN
Meunier, Ty	LW	5'9	159	L	CDN
Olson, Brett	C	6'1	185	R	CDN
Pavao, Cruz	RW	5'11	194	R	CDN
Ruck, Marcus	LW	5'11	168	L	CDN
Williams, Cooper	LW	6'0	150	L	CDN
Nyman, Zachary	D	5'9	165	L	CDN
Yellowaga, Nate	D	5'11	168	L	CDN
Brown, Ryan	LW	5'11	172	L	CDN
Smith, Brady	RW	6'0	181	R	CDN
Larys, Jan	G	6'2	159	L	CZE
Novak, Filip	LW	6'2	192	L	CZE
Alalauri, Samu	D	6'2	198	R	FIN
Kahkonen, Viijo	RW	5'10	179	R	FIN
Laatikainen, Max	D	5'10	157	R	FIN
Parssinen, Jesse	C	5'11	185	L	FIN
Poletin, Frantisek	G	6'2	183	R	CZE
Rajala, Joonas	LW	5'9	174	L	FIN
Rinne, Rasmus	LW	5'10	174	L	FIN
Svensk, Vertti	D	6'0	165	L	FIN
Uronen, Eelis	D	6'0	187	L	FIN
Virtanen, Jeremi	RW	5'11	179	L	FIN
Wahlroos, Olli	LW	6'0	187	L	FIN
Dolgopolov, Ilya	D	6'0	187	L	RUS
Fedoseyev, Yaroslav	D	6'1	181	R	RUS
Ivanov, Alexander	D	6'2	179	L	RUS
Kotkov, Matvei	LW	5'11	154	L	RUS
Matyev, Yaroslav	D	6'4	218	L	RUS
Achermann, Raphael	LW	5'11	172	L	SUI
Dube, Liam	C	5'10	159	R	SUI
Goljer, Adam	D	6'1	194	R	SVK
Hrenak, Samuel	G	6'2	176	L	SVK
Loob Trygg, Linus	RW	6'0	168	L	NOR
Anderberg, Morgan	C	5'11	174	L	SWE
Bartholdsson, Nils	RW	5'9	165	R	SWE
Brongel-Larsson, Axel	D	6'1	187	L	NOR
Elofsson, Axel	D	5'10	161	R	SWE
Hakansson, William	D	6'4	207	L	SWE
Isaksson, Max	C	6'0	183	L	SWE
Josbrant, Mans	LW	5'10	172	L	SWE
Lagerberg Hoen, Jonas	RW	6'2	176	R	SWE
Lindberg, Dennis	D	6'3	201	R	SWE
Palme, Ola	D	6'0	181	L	SWE
Klaucans, Martins	LW	6'0	181	L	LAT
Beuker, Dayne	C	5'10	161	R	USA
Boettiger, Harrison	G	6'2	185	L	USA
Francisco, AJ	D	5'11	181	R	USA
Hafele, Landon	LW	6'0	187	L	USA
Kemps, Jonas	D	6'6	183	L	USA
Kuehne, Lincoln	D	6'2	201	R	USA
Lutner, Logan	D	5'10	172	R	USA
Stuart, Logan	RW	5'10	163	R	USA
Trottier, Parker	LW	6'0	170	L	USA
Zajic, Lucas	RW	5'10	174	R	USA
Berzkalns, Rudolfs	LW	6'2	192	L	LAT
Bumgarner, Cole	G	6'0	198	L	USA
Croskery, Callum	D	6'0	174	L	CDN
Fedotov, Nikita	D	6'0	174	R	RUS
Jennersjo, Torkel	C	5'10	176	L	SWE
Klyopov, Nikita	LW	5'11	161	L	RUS
Kwajah, Jet	D	6'0	170	R	CDN
Laylin, Bode	D	5'11	174	R	USA
Vandenberg, Thomas	C	5'11	170	L	CDN
"""

from name_utils import canonical_key, html_unescape, normalize


def parse_height(h: str) -> float:
    if h in ("NA", "", None):
        return 72.0
    m = re.match(r"(\d)'(\d+)", h)
    if m:
        return int(m.group(1)) * 12 + int(m.group(2))
    return 72.0


def parse_weight(w: str) -> int:
    if w in ("NA", "", None):
        return 180
    try:
        return int(w)
    except ValueError:
        return 180


@dataclass
class Player:
    last: str
    first: str
    pos: str
    height: str
    weight: str
    shoots: str
    country: str
    birth_date: date | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"

    @property
    def slug(self) -> str:
        n = normalize(f"{self.last}_{self.first}")
        return re.sub(r"[^a-z0-9_]", "", n.replace(" ", "_"))

    @property
    def key(self) -> str:
        return canonical_key(self.full_name)


def parse_players(raw: str) -> list[Player]:
    players = []
    seen = set()
    for line in raw.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        name_parts = parts[0].split(",", 1)
        if len(name_parts) < 2:
            continue
        last, first = name_parts[0].strip(), name_parts[1].strip()
        key = canonical_key(f"{first} {last}")
        if key in seen:
            continue
        seen.add(key)
        pos = parts[1].strip()
        height = parts[2].strip()
        weight = parts[3].strip()
        shoots = parts[4].strip() or "?"
        country = parts[5].strip().replace("CDN", "CAN")
        dob = parse_dob(parts[6].strip()) if len(parts) > 6 else None
        players.append(
            Player(
                last=html_unescape(last),
                first=html_unescape(first),
                pos=pos,
                height=height,
                weight=weight,
                shoots=shoots,
                country=country,
                birth_date=dob,
            )
        )
    return players


def load_players() -> list[Player]:
    """Charge le pool éligible (TSV par repêchage) ou RAW_PLAYERS en secours."""
    tsv = ELIGIBLE_TSV
    if not tsv.exists():
        legacy = BASE / "data" / "eligible_players.tsv"
        if legacy.exists():
            tsv = legacy
    raw = tsv.read_text(encoding="utf-8") if tsv.exists() else RAW_PLAYERS
    players = parse_players(raw)
    eligible = []
    skipped = []
    for p in players:
        ok = is_draft_eligible_2026(p.birth_date, p.country)
        if ok is False:
            skipped.append(p)
            continue
        eligible.append(p)
    if skipped:
        print(f"Exclus (non éligibles DOB): {len(skipped)}")
        for p in skipped[:5]:
            print(f"  - {p.full_name} ({p.birth_date})")
    source = tsv.name if tsv.exists() else "RAW_PLAYERS"
    print(f"Source: {source}")
    return eligible


def write_player_doc(
    p: Player,
    final_rank: int,
    ns_rank: int,
    scores: dict,
    final_overall: float,
    consensus_rank,
) -> Path:
    OUT_DOCS.mkdir(parents=True, exist_ok=True)
    path = OUT_DOCS / f"{final_rank:03d}_{p.slug}.md"
    overall = final_overall
    cr = consensus_rank if consensus_rank else "N/A"
    star_tier = scores.get("star_tier", "N/A")
    cov = scores.get("report_coverage", "unknown")

    lines = [
        f"# Analyse NORTHSTAR: {p.full_name}",
        f"**Repêchage NHL 2026 — Rang FINAL: #{final_rank}**",
        "",
        "## Informations",
        "| Champ | Valeur |",
        "|-------|--------|",
        f"| Position | {p.pos} |",
        f"| Taille | {p.height} |",
        f"| Poids | {p.weight} lbs |",
        f"| Tire | {p.shoots} |",
        f"| Pays | {p.country} |",
        f"| Date naissance | {p.birth_date.isoformat() if p.birth_date else 'N/A'} |",
        f"| Couverture rapport | {cov} |",
        f"| **Rang FINAL (NORTHSTAR)** | **#{final_rank}** |",
        f"| Rang NORTHSTAR (score pur) | #{ns_rank} |",
        f"| Rang consensus public | {cr} |",
        f"| **Star Probability Index** | **{overall}/100** |",
        f"| Tier étoile estimé | {star_tier} |",
        "",
        "## Résumé exécutif",
        scores.get("resume", ""),
        "",
        "## Thèse star NORTHSTAR",
        scores.get("star_thesis", scores.get("upside_thesis", "")),
        "",
        "## Grille NORTHSTAR (7 piliers — basée sur rapports scouting)",
        "",
        "| Dimension | Note /10 | Poids | Score |",
        "|-----------|----------|-------|-------|",
    ]
    for cat, label in NORTHSTAR_LABELS.items():
        note = scores.get(cat, 5.0)
        w = NORTHSTAR_WEIGHTS[cat]
        lines.append(f"| {label} | {note} | {w*100:.0f}% | {note*w*10:.2f} |")

    lines.extend([
        "",
        f"**STAR PROBABILITY INDEX: {overall}/100**",
        "",
        "## Justification détaillée des notes",
        "",
    ])
    rationales = scores.get("rationales") or {}
    for cat, label in NORTHSTAR_LABELS.items():
        note = scores.get(cat, 5.0)
        text = rationales.get(cat, "")
        lines.append(f"### {label} — {note}/10")
        lines.append(text if text else "_Justification non disponible._")
        lines.append("")

    lines.extend([
        "## Forces (signaux star)",
    ])
    for f in scores.get("forces", []):
        lines.append(f"- {f}")

    lines.extend(["", "## Faiblesses / risques"])
    for f in scores.get("faiblesses", []):
        lines.append(f"- {f}")

    lines.extend([
        "",
        "## Projection NHL",
        scores.get("projection", "N/A"),
        "",
        "## Méthodologie NORTHSTAR",
        "Le **rang FINAL** est le classement pur par **Star Probability Index** (score NORTHSTAR). "
        "Chaque joueur est évalué à partir de son rapport de scouting DPH quand disponible, "
        "via analyse textuelle de 7 piliers prédictifs de stardom NHL. "
        "Le consensus public est affiché à titre de référence uniquement.",
        "",
        "---",
        "*Modèle NORTHSTAR — refonte complète basée sur rapports de scouting.*",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def find_consensus_rank(p: Player) -> int | None:
    for name, rank in CONSENSUS_RANKS.items():
        if normalize(name) == p.key or normalize(name) == normalize(p.full_name):
            return rank
    # fuzzy last name match for variants
    for name, rank in CONSENSUS_RANKS.items():
        if normalize(p.last) in normalize(name) and normalize(p.first) in normalize(name):
            return rank
    return None


def main():
    players = load_players()
    print(f"Joueurs uniques: {len(players)}")

    if OUT_DOCS.exists():
        for f in OUT_DOCS.glob("*.md"):
            f.unlink()

    # Étape 1 — score NORTHSTAR pur (rapports scouting)
    ns_items = []
    for p in players:
        cr = find_consensus_rank(p)
        scores = northstar_generate(
            p.full_name, p.pos, p.height, p.weight, p.country, cr, player_key=p.key
        )
        overall = northstar_overall(scores)
        ns_items.append({"p": p, "cr": cr, "scores": scores, "overall": overall})

    ns_items.sort(key=lambda x: (-x["overall"], x["p"].full_name))
    for i, item in enumerate(ns_items, 1):
        item["ns_rank"] = i
        item["final_rank"] = i  # rang FINAL = rang NORTHSTAR pur

    rows = []
    for item in ns_items:
        p = item["p"]
        cr = item["cr"]
        scores = item["scores"]
        overall = item["overall"]
        nr = item["ns_rank"]
        fr = item["final_rank"]
        doc_path = write_player_doc(p, fr, nr, scores, overall, cr)
        doc_url = f"https://drive.google.com/file/d/PLACEHOLDER_{p.slug}/view"
        row = {
            "Rang_Final": fr,
            "Rang_NORTHSTAR": nr,
            "Nom": p.full_name,
            "Position": p.pos,
            "Taille": p.height,
            "Poids_lbs": p.weight,
            "Tire": p.shoots,
            "Pays": p.country,
            "Date_Naissance": p.birth_date.isoformat() if p.birth_date else "",
            "Score_NORTHSTAR": overall,
            "Star_Tier": scores.get("star_tier", ""),
            "Couverture_Rapport": scores.get("report_coverage", ""),
            "Rang_Consensus": cr if cr is not None else "N/A",
            "Delta_vs_Consensus": (cr - fr) if cr else "N/A",
            "Plafond_Etoile": scores.get("star_ceiling"),
            "IQ_Elite": scores.get("hockey_iq"),
            "Moteur_Patinage": scores.get("skating_engine"),
            "Pouvoir_Offensif": scores.get("offensive_star_power"),
            "Preuve_Competition": scores.get("competition_proof"),
            "Competitivite": scores.get("character_compete"),
            "Arc_Developpement": scores.get("development_arc"),
            "Rationales": scores.get("rationales", {}),
            "Lien_Analyse": doc_url,
            "Fichier_Local": str(doc_path.relative_to(BASE)),
            # compatibilité site (aliases)
            "Rang_APEX": nr,
            "Moyenne_Rang": float(nr),
            "Score_APEX": overall,
            "Plafond_Elite": scores.get("star_ceiling"),
            "Patinage_Upside": scores.get("skating_engine"),
            "Outils_Offensifs": scores.get("offensive_star_power"),
            "Creation_Jeu": scores.get("offensive_star_power"),
            "IQ_Realisation": scores.get("hockey_iq"),
            "Trajectoire": scores.get("development_arc"),
            "Variance_Positive": scores.get("character_compete"),
        }
        rows.append(row)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"CSV: {OUT_CSV}")
    print(f"Analyses: {OUT_DOCS} ({len(rows)} fichiers)")
    print(f"Top 15 FINAL (NORTHSTAR Star Probability):")
    for r in rows[:15]:
        cr = r["Rang_Consensus"]
        ds = f" (consensus #{cr}, delta {r['Delta_vs_Consensus']})" if cr != "N/A" else ""
        print(f"  #{r['Rang_Final']} {r['Nom']} - SPI {r['Score_NORTHSTAR']}/100 [{r['Star_Tier']}]{ds}")

    cov_counts: dict[str, int] = {}
    for r in rows:
        c = r.get("Couverture_Rapport") or "unknown"
        cov_counts[c] = cov_counts.get(c, 0) + 1
    print(f"\nCouverture rapports DPH ({len(rows)} joueurs):")
    for k in ("full", "partial", "thin", "none"):
        print(f"  {k}: {cov_counts.get(k, 0)}")


if __name__ == "__main__":
    main()
