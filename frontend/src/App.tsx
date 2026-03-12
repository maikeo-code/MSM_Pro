import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Dashboard from "@/pages/Dashboard";
import Anuncios from "@/pages/Anuncios";
import AnuncioDetalhe from "@/pages/Anuncios/AnuncioDetalhe";
import Concorrencia from "@/pages/Concorrencia";
import Alertas from "@/pages/Alertas";
import Configuracoes from "@/pages/Configuracoes";
import Produtos from "@/pages/Produtos";
import Login from "@/pages/Login";
import Layout from "@/components/Layout";
import ProtectedRoute from "@/components/ProtectedRoute";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/anuncios" element={<Anuncios />} />
            <Route path="/anuncios/:mlbId" element={<AnuncioDetalhe />} />
            <Route path="/produtos" element={<Produtos />} />
            <Route path="/concorrencia" element={<Concorrencia />} />
            <Route path="/alertas" element={<Alertas />} />
            <Route path="/configuracoes" element={<Configuracoes />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
