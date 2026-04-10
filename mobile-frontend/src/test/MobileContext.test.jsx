import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { MobileProviders, useApp, useAuth } from "../contexts/MobileContext";
import mobileApiClient from "../lib/mobileApi";

vi.mock("../lib/mobileApi");

const TestAuthComponent = () => {
  const { user, isAuthenticated, loading } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="authenticated">{String(isAuthenticated)}</span>
      <span data-testid="user">{user?.email || "none"}</span>
    </div>
  );
};

const TestAppComponent = () => {
  const { theme, toggleTheme, isOnline, notifications } = useApp();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <span data-testid="online">{String(isOnline)}</span>
      <span data-testid="notifications">{notifications.length}</span>
      <button onClick={toggleTheme}>Toggle Theme</button>
    </div>
  );
};

const wrapper = ({ children }) => (
  <BrowserRouter>
    <MobileProviders>{children}</MobileProviders>
  </BrowserRouter>
);

describe("MobileContext - AuthProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.getItem.mockReturnValue(null);
    mobileApiClient.getProfile = vi.fn();
    mobileApiClient.setToken = vi.fn();
    mobileApiClient.clearCache = vi.fn();
    mobileApiClient.logout = vi.fn().mockResolvedValue(undefined);
    mobileApiClient.login = vi.fn();
    mobileApiClient.register = vi.fn();
  });

  it("starts with loading true then resolves to unauthenticated", async () => {
    render(<TestAuthComponent />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });

    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(screen.getByTestId("user").textContent).toBe("none");
  });

  it("loads user profile when token exists in localStorage", async () => {
    localStorage.getItem.mockReturnValue("saved-token");
    mobileApiClient.getProfile.mockResolvedValue({
      email: "user@example.com",
      first_name: "Test",
    });

    render(<TestAuthComponent />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId("authenticated").textContent).toBe("true");
    });

    expect(screen.getByTestId("user").textContent).toBe("user@example.com");
  });

  it("logs out when profile load fails", async () => {
    localStorage.getItem.mockReturnValue("bad-token");
    mobileApiClient.getProfile.mockRejectedValue(new Error("Unauthorized"));

    render(<TestAuthComponent />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId("authenticated").textContent).toBe("false");
    });
  });
});

describe("MobileContext - AppProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.getItem.mockReturnValue(null);
    mobileApiClient.getProfile = vi.fn();
  });

  it("renders with default light theme", async () => {
    render(<TestAppComponent />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId("theme").textContent).toBe("light");
    });
  });

  it("toggles theme on button click", async () => {
    const user = userEvent.setup();
    render(<TestAppComponent />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId("theme").textContent).toBe("light");
    });

    await user.click(screen.getByText("Toggle Theme"));

    expect(screen.getByTestId("theme").textContent).toBe("dark");
    expect(localStorage.setItem).toHaveBeenCalledWith("theme", "dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("shows online status", async () => {
    render(<TestAppComponent />, { wrapper });

    await waitFor(() => {
      expect(screen.getByTestId("online").textContent).toBe("true");
    });
  });
});
