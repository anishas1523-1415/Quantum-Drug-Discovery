import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import ProtectedRoute from "./ProtectedRoute";

const useAuthMock = vi.fn();

vi.mock("../context/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

function renderWithRoute() {
  return render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <div>Secret Dashboard</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>
  );
}

function renderWithAdminRoute(initialEntry = "/admin") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/dashboard" element={<div>Regular Dashboard</div>} />
        <Route
          path="/admin"
          element={
            <ProtectedRoute requireRole="admin">
              <div>Admin Panel</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>
  );
}

describe("ProtectedRoute", () => {
  it("redirects to /login when not authenticated", () => {
    useAuthMock.mockReturnValue({ isAuthenticated: false, initializing: false });

    renderWithRoute();

    expect(screen.getByText("Login Page")).toBeInTheDocument();
    expect(screen.queryByText("Secret Dashboard")).not.toBeInTheDocument();
  });

  it("renders the protected content when authenticated", () => {
    useAuthMock.mockReturnValue({ isAuthenticated: true, initializing: false });

    renderWithRoute();

    expect(screen.getByText("Secret Dashboard")).toBeInTheDocument();
  });

  it("shows a loader while auth state is initializing", () => {
    useAuthMock.mockReturnValue({ isAuthenticated: false, initializing: true });

    renderWithRoute();

    expect(screen.queryByText("Secret Dashboard")).not.toBeInTheDocument();
    expect(screen.queryByText("Login Page")).not.toBeInTheDocument();
  });

  it("redirects a non-admin user away from an admin-only route", () => {
    useAuthMock.mockReturnValue({
      isAuthenticated: true,
      initializing: false,
      user: { role: "doctor" },
    });

    renderWithAdminRoute();

    expect(screen.getByText("Regular Dashboard")).toBeInTheDocument();
    expect(screen.queryByText("Admin Panel")).not.toBeInTheDocument();
  });

  it("allows an admin user onto an admin-only route", () => {
    useAuthMock.mockReturnValue({
      isAuthenticated: true,
      initializing: false,
      user: { role: "admin" },
    });

    renderWithAdminRoute();

    expect(screen.getByText("Admin Panel")).toBeInTheDocument();
  });
});
