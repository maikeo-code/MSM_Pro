import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Dashboard from "@/pages/Dashboard";
import Anuncios from "@/pages/Anuncios";
import AnuncioDetalhe from "@/pages/Anuncios/AnuncioDetalhe";
import AnaliseAnuncios from "@/pages/AnaliseAnuncios";
import Concorrencia from "@/pages/Concorrencia";
import Alertas from "@/pages/Alertas";
import Configuracoes from "@/pages/Configuracoes";
import Reputacao from "@/pages/Reputacao";
import Produtos from "@/pages/Produtos";
import Pedidos from "@/pages/Pedidos";
import Perguntas from "@/pages/Perguntas";
import Login from "@/pages/Login";
import Layout from "@/components/Layout";
import ProtectedRoute from "@/components/ProtectedRoute";

const Financeiro = lazy(() => import("@/pages/Financeiro"));
const Publicidade = lazy(() => import("@/pages/Publicidade"));

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
            <Route path="/pedidos" element={<Pedidos />} />
            <Route path="/perguntas" element={<Perguntas />} />
            <Route path="/analise-anuncios" element={<AnaliseAnuncios />} />
            <Route path="/produtos" element={<Produtos />} />
            <Route path="/concorrencia" element={<Concorrencia />} />
            <Route path="/alertas" element={<Alertas />} />
            <Route path="/reputacao" element={<Reputacao />} />
            <Route
              path="/financeiro"
              element={
                <Suspense fallback={<div className="p-8 text-gray-400">Carregando...</div>}>
                  <Financeiro />
                </Suspense>
              }
            />
            <Route
              path="/publicidade"
              element={
                <Suspense fallback={<div className="p-8 text-gray-400">Carregando...</div>}>
                  <Publicidade />
                </Suspense>
              }
            />
            <Route path="/configuracoes" element={<Configuracoes />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
