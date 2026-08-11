import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import client from "../api/client";
import { AuthProvider, useAuth } from "./AuthContext";

vi.mock("../api/client", () => ({
  default: { get: vi.fn(), post: vi.fn() },
  extractErrorMessage: (error) => error?.response?.data?.message || "Something went wrong",
}));

function Consumer() {
  const { isAuthenticated, user, login, logout, initializing } = useAuth();

  if (initializing) return <div>loading</div>;

  return (
    <div>
      <div data-testid="status">{isAuthenticated ? "in" : "out"}</div>
      <div data-testid="user">{user?.name || "none"}</div>
      <button onClick={() => login("doctor@gmail.com", "password123")}>login</button>
      <button onClick={() => login("doctor@gmail.com", "wrong")}>login-bad</button>
      <button onClick={logout}>logout</button>
    </div>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe("AuthContext", () => {
  it("starts logged out with no stored token", async () => {
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("out"));
  });

  it("logs in successfully and persists the session", async () => {
    client.post.mockResolvedValueOnce({
      data: { token: "fake-jwt", user: { id: 1, name: "Dr. Demo", email: "doctor@gmail.com" } },
    });

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("out"));

    await act(async () => {
      await userEvent.click(screen.getByText("login"));
    });

    expect(screen.getByTestId("status")).toHaveTextContent("in");
    expect(screen.getByTestId("user")).toHaveTextContent("Dr. Demo");
    expect(localStorage.getItem("qdd_token")).toBe("fake-jwt");
  });

  it("does not authenticate on failed login", async () => {
    client.post.mockRejectedValueOnce({ response: { data: { message: "Invalid email or password" } } });

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("out"));

    await act(async () => {
      await userEvent.click(screen.getByText("login-bad"));
    });

    expect(screen.getByTestId("status")).toHaveTextContent("out");
    expect(localStorage.getItem("qdd_token")).toBeNull();
  });

  it("clears the session on logout", async () => {
    client.post.mockResolvedValueOnce({
      data: { token: "fake-jwt", user: { id: 1, name: "Dr. Demo", email: "doctor@gmail.com" } },
    });

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("out"));

    await act(async () => {
      await userEvent.click(screen.getByText("login"));
    });

    expect(screen.getByTestId("status")).toHaveTextContent("in");

    await act(async () => {
      await userEvent.click(screen.getByText("logout"));
    });

    expect(screen.getByTestId("status")).toHaveTextContent("out");
    expect(localStorage.getItem("qdd_token")).toBeNull();
  });

  it("restores and verifies a session from a stored token", async () => {
    localStorage.setItem("qdd_token", "existing-token");
    localStorage.setItem("qdd_user", JSON.stringify({ id: 1, name: "Dr. Demo", email: "doctor@gmail.com" }));
    client.get.mockResolvedValueOnce({ data: { user: { id: 1, name: "Dr. Demo", email: "doctor@gmail.com" } } });

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("in"));
  });

  it("logs out automatically when the stored token is rejected", async () => {
    localStorage.setItem("qdd_token", "stale-token");
    client.get.mockRejectedValueOnce({ response: { status: 401 } });

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("out"));
    expect(localStorage.getItem("qdd_token")).toBeNull();
  });
});
