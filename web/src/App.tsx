import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Home from "@/pages/Home";
import Login from "@/pages/Login";
import ImageStudio from "@/pages/ImageStudio";
import CanvasPage from "@/pages/CanvasPage";
import PlatformLayout from "@/components/PlatformLayout";
import RequireAuth from "@/components/RequireAuth";
import Dashboard from "@/pages/Dashboard";
import Copywriting from "@/pages/Copywriting";
import Products from "@/pages/Products";
import Assets from "@/pages/Assets";
import Marketing from "@/pages/Marketing";
import Service from "@/pages/Service";
import Finance from "@/pages/Finance";

export default function App() {
  return (
    <Router>
      <Routes>
        {/* 登录页（公开） */}
        <Route path="/login" element={<Login />} />

        {/* AI 语音助手（需要登录） */}
        <Route
          path="/"
          element={
            <RequireAuth>
              <Home />
            </RequireAuth>
          }
        />

        {/* 无限画布（需要登录） */}
        <Route
          path="/canvas"
          element={
            <RequireAuth>
              <CanvasPage />
            </RequireAuth>
          }
        />

        {/* 电商老板多功能平台（需要登录） */}
        <Route
          path="/platform"
          element={
            <RequireAuth>
              <PlatformLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="image" element={<ImageStudio />} />
          <Route path="copywriting" element={<Copywriting />} />
          <Route path="products" element={<Products />} />
          <Route path="assets" element={<Assets />} />
          <Route path="marketing" element={<Marketing />} />
          <Route path="service" element={<Service />} />
          <Route path="finance" element={<Finance />} />
        </Route>

        {/* 兼容旧路由（需要登录） */}
        <Route
          path="/studio"
          element={
            <RequireAuth>
              <ImageStudio />
            </RequireAuth>
          }
        />
      </Routes>
    </Router>
  );
}
