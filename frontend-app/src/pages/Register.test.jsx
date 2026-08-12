import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Register from "./Register";

const registerMock = vi.fn();

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({ register: registerMock }),
}));

vi.mock("../context/ToastContext", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

beforeEach(() => {
  registerMock.mockReset();
});

function renderRegister() {
  return render(
    <MemoryRouter>
      <Register />
    </MemoryRouter>
  );
}

describe("Register page", () => {
  it("rejects a password shorter than 6 characters", async () => {
    renderRegister();

    await userEvent.type(screen.getByPlaceholderText("Dr. Jane Smith"), "Dr. Jane Smith");
    await userEvent.type(screen.getByPlaceholderText("doctor@example.com"), "jane@example.com");
    await userEvent.type(screen.getByPlaceholderText("At least 6 characters"), "123");
    await userEvent.type(screen.getByPlaceholderText("Re-enter password"), "123");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByText("Use at least 6 characters")).toBeInTheDocument();
    expect(registerMock).not.toHaveBeenCalled();
  });

  it("rejects mismatched passwords", async () => {
    renderRegister();

    await userEvent.type(screen.getByPlaceholderText("Dr. Jane Smith"), "Dr. Jane Smith");
    await userEvent.type(screen.getByPlaceholderText("doctor@example.com"), "jane@example.com");
    await userEvent.type(screen.getByPlaceholderText("At least 6 characters"), "securepass1");
    await userEvent.type(screen.getByPlaceholderText("Re-enter password"), "differentpass");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByText("Passwords do not match")).toBeInTheDocument();
    expect(registerMock).not.toHaveBeenCalled();
  });

  it("submits with the doctor role by default", async () => {
    registerMock.mockResolvedValueOnce({ ok: true });
    renderRegister();

    await userEvent.type(screen.getByPlaceholderText("Dr. Jane Smith"), "Dr. Jane Smith");
    await userEvent.type(screen.getByPlaceholderText("doctor@example.com"), "jane@example.com");
    await userEvent.type(screen.getByPlaceholderText("At least 6 characters"), "securepass1");
    await userEvent.type(screen.getByPlaceholderText("Re-enter password"), "securepass1");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(registerMock).toHaveBeenCalledWith("Dr. Jane Smith", "jane@example.com", "securepass1", "doctor");
  });

  it("submits with the researcher role when selected", async () => {
    registerMock.mockResolvedValueOnce({ ok: true });
    renderRegister();

    await userEvent.type(screen.getByPlaceholderText("Dr. Jane Smith"), "Dr. Jane Smith");
    await userEvent.type(screen.getByPlaceholderText("doctor@example.com"), "jane@example.com");
    await userEvent.type(screen.getByPlaceholderText("At least 6 characters"), "securepass1");
    await userEvent.type(screen.getByPlaceholderText("Re-enter password"), "securepass1");
    await userEvent.click(screen.getByRole("button", { name: "Researcher" }));
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(registerMock).toHaveBeenCalledWith("Dr. Jane Smith", "jane@example.com", "securepass1", "researcher");
  });
});
