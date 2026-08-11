import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Login from "./Login";

const loginMock = vi.fn();
const toastErrorMock = vi.fn();

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({ login: loginMock }),
}));

vi.mock("../context/ToastContext", () => ({
  useToast: () => ({ success: vi.fn(), error: toastErrorMock }),
}));

beforeEach(() => {
  loginMock.mockReset();
  toastErrorMock.mockReset();
});

function renderLogin() {
  return render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>
  );
}

describe("Login page", () => {
  it("shows validation errors on empty submit and does not call login", async () => {
    renderLogin();

    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("Email is required")).toBeInTheDocument();
    expect(screen.getByText("Password is required")).toBeInTheDocument();
    expect(loginMock).not.toHaveBeenCalled();
  });

  it("submits valid credentials", async () => {
    loginMock.mockResolvedValueOnce({ ok: true });
    renderLogin();

    await userEvent.type(screen.getByPlaceholderText("doctor@example.com"), "doctor@gmail.com");
    await userEvent.type(screen.getByPlaceholderText("••••••••"), "password123");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(loginMock).toHaveBeenCalledWith("doctor@gmail.com", "password123");
  });

  it("toggles password visibility", async () => {
    renderLogin();

    const passwordInput = screen.getByPlaceholderText("••••••••");
    expect(passwordInput).toHaveAttribute("type", "password");

    await userEvent.click(screen.getByRole("button", { name: /show password/i }));

    expect(passwordInput).toHaveAttribute("type", "text");
  });
});
