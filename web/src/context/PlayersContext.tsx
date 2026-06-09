import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { Player } from "../types/player";

interface PlayersContextValue {
  players: Player[];
  loading: boolean;
  error: string | null;
  getPlayer: (id: string) => Player | undefined;
}

const PlayersContext = createContext<PlayersContextValue | null>(null);

export function PlayersProvider({ children }: { children: ReactNode }) {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/data/players.json")
      .then((r) => {
        if (!r.ok) throw new Error("Impossible de charger les données");
        return r.json();
      })
      .then(setPlayers)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const getPlayer = (id: string) => players.find((p) => p.id === id);

  return (
    <PlayersContext.Provider value={{ players, loading, error, getPlayer }}>
      {children}
    </PlayersContext.Provider>
  );
}

export function usePlayers() {
  const ctx = useContext(PlayersContext);
  if (!ctx) throw new Error("usePlayers must be used within PlayersProvider");
  return ctx;
}
