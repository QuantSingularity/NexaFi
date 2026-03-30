import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MobileAuthPage from "../components/MobileAuthPage";
import { MobileProviders } from "../contexts/MobileContext";

const wrapper = ({ children }) => (
  <BrowserRouter>
    <MobileProviders>{children}</MobileProviders>
  </BrowserRouter>
);

describe("MobileAuthPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders login form by default", () => {
    render(<MobileAuthPage />, { wrapper });

    expect(screen.getByText(/Sign in to your account/i)).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/Enter your email/i),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/Enter your password/i),
    ).toBeInTheDocument();
  });

  it("switches to register form when clicking Sign Up tab", async () => {
    const user = userEvent.setup();
    render(<MobileAuthPage />, { wrapper });

    const signUpTab = screen.getByRole("tab", { name: /sign up/i });
    await user.click(signUpTab);

    expect(screen.getByText(/Create your account/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/First name/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Last name/i)).toBeInTheDocument();
  });

  it("shows password when clicking eye icon", async () => {
    const user = userEvent.setup();
    render(<MobileAuthPage />, { wrapper });

    const passwordInput = screen.getByPlaceholderText(/Enter your password/i);
    expect(passwordInput).toHaveAttribute("type", "password");

    const eyeButton = screen.getAllByRole("button")[0]; // First button should be eye icon
    await user.click(eyeButton);

    await waitFor(() => {
      expect(passwordInput).toHaveAttribute("type", "text");
    });
  });

  it("validates required fields on login", async () => {
    const user = userEvent.setup();
    render(<MobileAuthPage />, { wrapper });

    const loginButton = screen.getByRole("button", { name: /sign in/i });
    await user.click(loginButton);

    await waitFor(() => {
      expect(
        screen.getByText(/please fill in all fields/i),
      ).toBeInTheDocument();
    });
  });

  it("validates password match on registration", async () => {
    const user = userEvent.setup();
    render(<MobileAuthPage />, { wrapper });

    // Switch to sign up
    const signUpTab = screen.getByRole("tab", { name: /sign up/i });
    await user.click(signUpTab);

    // Fill in fields with non-matching passwords
    await user.type(screen.getByPlaceholderText(/First name/i), "John");
    await user.type(screen.getByPlaceholderText(/Last name/i), "Doe");
    await user.type(
      screen.getByPlaceholderText(/Enter your email/i),
      "john@example.com",
    );
    await user.type(
      screen.getByPlaceholderText(/Create a password/i),
      "password123",
    );
    await user.type(
      screen.getByPlaceholderText(/Confirm your password/i),
      "password456",
    );

    const signUpButton = screen.getByRole("button", {
      name: /create account/i,
    });
    await user.click(signUpButton);

    await waitFor(() => {
      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
    });
  });
});
