import { Navigate } from "react-router-dom";

export function DashboardPage() {
  // Dashboard redirects to screener for MVP
  return <Navigate to="/screener" replace />;
}
