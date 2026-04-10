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

  it("shows password when clicking eye icon on login form", async () => {
    const user = userEvent.setup();
    render(<MobileAuthPage />, { wrapper });

    const passwordInput = screen.getByPlaceholderText(/Enter your password/i);
    expect(passwordInput).toHaveAttribute("type", "password");

    const eyeButton = screen.getByLabelText(/Show password/i);
    await user.click(eyeButton);

    await waitFor(() => {
      expect(passwordInput).toHaveAttribute("type", "text");
    });
  });

  it("hides password when clicking eye icon again", async () => {
    const user = userEvent.setup();
    render(<MobileAuthPage />, { wrapper });

    const eyeButton = screen.getByLabelText(/Show password/i);
    await user.click(eyeButton);

    await waitFor(() => {
      expect(screen.getByLabelText(/Hide password/i)).toBeInTheDocument();
    });

    await user.click(screen.getByLabelText(/Hide password/i));

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText(/Enter your password/i),
      ).toHaveAttribute("type", "password");
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

    const signUpTab = screen.getByRole("tab", { name: /sign up/i });
    await user.click(signUpTab);

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

  it("shows Back button that navigates to home", () => {
    render(<MobileAuthPage />, { wrapper });
    expect(screen.getByRole("button", { name: /back/i })).toBeInTheDocument();
  });

  it("clears error when switching tabs", async () => {
    const user = userEvent.setup();
    render(<MobileAuthPage />, { wrapper });

    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => {
      expect(
        screen.getByText(/please fill in all fields/i),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("tab", { name: /sign up/i }));
    await user.click(screen.getByRole("tab", { name: /sign in/i }));

    expect(
      screen.queryByText(/please fill in all fields/i),
    ).not.toBeInTheDocument();
  });
});
