import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import HomePage from "./pages/HomePage";
import PlayerPage from "./pages/PlayerPage";
import ComparePage from "./pages/ComparePage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/player/:id" element={<PlayerPage />} />
        <Route path="/compare" element={<ComparePage />} />
      </Route>
    </Routes>
  );
}
