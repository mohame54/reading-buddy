import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { checkHealth } from "../api/client";
import { AppShell } from "../components/Layout";

export function HomePage() {
  const [healthy, setHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    checkHealth().then(setHealthy);
  }, []);

  return (
    <>
      <AppShell />
      <main className="home">
        <h1>Reading Buddy</h1>
        <p>Arabic reading practice with pronunciation feedback.</p>
        {healthy === false && (
          <p className="error-banner">API is unreachable. Check that the backend is running.</p>
        )}
        <div className="home-links">
          <Link to="/admin" className="home-card">
            <h2>Admin</h2>
            <p>Upload books, manage content</p>
          </Link>
          <Link to="/users" className="home-card">
            <h2>Users</h2>
            <p>Browse library and read aloud</p>
          </Link>
        </div>
      </main>
    </>
  );
}
