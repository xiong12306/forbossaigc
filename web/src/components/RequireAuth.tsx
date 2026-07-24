import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { isLoggedIn } from "@/lib/auth";

interface Props {
  children: React.ReactNode;
}

export default function RequireAuth({ children }: Props) {
  const location = useLocation();
  const [authed, setAuthed] = useState<boolean>(isLoggedIn());

  useEffect(() => {
    setAuthed(isLoggedIn());
  }, [location.pathname]);

  if (!authed) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
