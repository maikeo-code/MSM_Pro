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
import Atendimento from "@/pages/Atendimento";
import Login from "@/pages/Login";
import Layout from "@/components/Layout";
import ProtectedRoute from "@/components/ProtectedRoute";
import { ErrorBoundary } from "@/components/ErrorBoundary";

const PriceSuggestions = lazy(() => import("@/pages/PriceSuggestions"));
const Financeiro = lazy(() => import("@/pages/Financeiro"));
const Publicidade = lazy(() => import("@/pages/Publicidade"));
const Intel = lazy(() => import("@/pages/Intel"));
const ParetoChart = lazy(() => import("@/pages/Intel/Analytics/ParetoChart"));
const SalesForecast = lazy(() => import("@/pages/Intel/Analytics/SalesForecast"));
const SalesDistribution = lazy(() => import("@/pages/Intel/Analytics/SalesDistribution"));
const InsightsPanel = lazy(() => import("@/pages/Intel/Analytics/InsightsPanel"));
const Comparison = lazy(() => import("@/pages/Intel/Analytics/Comparison"));
const ABC = lazy(() => import("@/pages/Intel/Analytics/ABC"));
const InventoryHealth = lazy(() => import("@/pages/Intel/Analytics/InventoryHealth"));

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<ErrorBoundary><Layout /></ErrorBoundary>}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/anuncios" element={<Anuncios />} />
            <Route path="/anuncios/:mlbId" element={<AnuncioDetalhe />} />
            <Route path="/pedidos" element={<Pedidos />} />
            <Route path="/atendimento" element={<Atendimento />} />
            <Route
              path="/precos"
              element={
                <Suspense fallback={<div className="p-8 text-gray-400">Carregando...</div>}>
                  <PriceSuggestions />
                </Suspense>
              }
            />
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
            <Route
              path="/intel"
              element={
                <Suspense fallback={<div className="p-8 text-gray-400">Carregando...</div>}>
                  <Intel />
                </Suspense>
              }
            />
            <Route
              path="/intel/pareto"
              element={
                <Suspense fallback={<div className="p-8 text-gray-400">Carregando...</div>}>
                  <ParetoChart />
                </Suspense>
              }
            />
            <Route
              path="/intel/forecast"
              element={
                <Suspense fallback={<div className="p-8 text-gray-400">Carregando...</div>}>
                  <SalesForecast />
                </Suspense>
              }
            />
            <Route
              path="/intel/distribution"
              element={
                <Suspense fallback={<div className="p-8 text-gray-400">Carregando...</div>}>
                  <SalesDistribution />
                </Suspense>
              }
            />
            <Route
              path="/intel/insights"
              element={
                <Suspense fallback={<div className="p-8 text-gray-400">Carregando...</div>}>
                  <InsightsPanel />
                </Suspense>
              }
            />
            <Route
              path="/intel/comparison"
              element={
                <Suspense fallback={<div className="p-8 text-gray-400">Carregando...</div>}>
                  <Comparison />
                </Suspense>
              }
            />
            <Route
              path="/intel/abc"
              element={
                <Suspense fallback={<div className="p-8 text-gray-400">Carregando...</div>}>
                  <ABC />
                </Suspense>
              }
            />
            <Route
              path="/intel/inventory"
              element={
                <Suspense fallback={<div className="p-8 text-gray-400">Carregando...</div>}>
                  <InventoryHealth />
                </Suspense>
              }
            />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
