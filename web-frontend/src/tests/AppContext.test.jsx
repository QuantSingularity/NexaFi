import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  AuthProvider,
  AppProvider,
  useAuth,
  useApp,
} from "../contexts/AppContext";
import apiClient from "../lib/api";

vi.mock("../lib/api", () => ({
  default: {
    setToken: vi.fn(),
    getUserProfile: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  },
}));

// Helper component to expose auth state
const AuthConsumer = ({ onRender }) => {
  const auth = useAuth();
  onRender(auth);
  return (
    <div>
      <span data-testid="authenticated">{String(auth.isAuthenticated)}</span>
      <span data-testid="loading">{String(auth.loading)}</span>
      <span data-testid="error">{auth.error || ""}</span>
      <span data-testid="user">{auth.user?.email || ""}</span>
    </div>
  );
};

const AppConsumer = ({ onRender }) => {
  const app = useApp();
  onRender(app);
  return (
    <div>
      <span data-testid="theme">{app.theme}</span>
      <span data-testid="notifications">{app.notifications.length}</span>
    </div>
  );
};

const renderWithAuth = (ui) =>
  render(
    <AppProvider>
      <AuthProvider>{ui}</AuthProvider>
    </AppProvider>,
  );

describe("AuthContext", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("starts unauthenticated with no user", () => {
    let captured = {};
    renderWithAuth(
      <AuthConsumer
        onRender={(v) => {
          captured = v;
        }}
      />,
    );
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(screen.getByTestId("user").textContent).toBe("");
  });

  it("restores session from localStorage token on mount", async () => {
    localStorage.setItem("access_token", "saved-token");
    apiClient.getUserProfile.mockResolvedValueOnce({
      user: { id: 1, email: "user@test.com", first_name: "Test" },
    });

    renderWithAuth(<AuthConsumer onRender={() => {}} />);

    await waitFor(() => {
      expect(screen.getByTestId("authenticated").textContent).toBe("true");
    });
    expect(apiClient.setToken).toHaveBeenCalledWith("saved-token");
    expect(screen.getByTestId("user").textContent).toBe("user@test.com");
  });

  it("clears token if profile fetch fails on mount", async () => {
    localStorage.setItem("access_token", "bad-token");
    apiClient.getUserProfile.mockRejectedValueOnce(new Error("Unauthorized"));

    renderWithAuth(<AuthConsumer onRender={() => {}} />);

    await waitFor(() => {
      expect(localStorage.getItem("access_token")).toBeNull();
    });
  });

  it("login sets authenticated state and stores token", async () => {
    apiClient.login.mockResolvedValueOnce({
      access_token: "new-token",
      user: { id: 2, email: "login@test.com", first_name: "Login" },
    });

    let authRef = {};
    renderWithAuth(
      <AuthConsumer
        onRender={(v) => {
          authRef = v;
        }}
      />,
    );

    await act(async () => {
      await authRef.login({ email: "login@test.com", password: "password123" });
    });

    expect(screen.getByTestId("authenticated").textContent).toBe("true");
    expect(screen.getByTestId("user").textContent).toBe("login@test.com");
  });

  it("login failure sets error state", async () => {
    apiClient.login.mockRejectedValueOnce(new Error("Invalid credentials"));

    let authRef = {};
    renderWithAuth(
      <AuthConsumer
        onRender={(v) => {
          authRef = v;
        }}
      />,
    );

    await act(async () => {
      try {
        await authRef.login({ email: "bad@test.com", password: "wrong" });
      } catch {
        // expected
      }
    });

    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(screen.getByTestId("error").textContent).toBe("Invalid credentials");
  });

  it("logout clears authenticated state", async () => {
    apiClient.login.mockResolvedValueOnce({
      access_token: "tok",
      user: { id: 1, email: "user@test.com" },
    });
    apiClient.logout.mockResolvedValueOnce({});

    let authRef = {};
    renderWithAuth(
      <AuthConsumer
        onRender={(v) => {
          authRef = v;
        }}
      />,
    );

    await act(async () => {
      await authRef.login({ email: "user@test.com", password: "pass" });
    });
    expect(screen.getByTestId("authenticated").textContent).toBe("true");

    await act(async () => {
      await authRef.logout();
    });
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(screen.getByTestId("user").textContent).toBe("");
  });

  it("logout clears token even if API call fails", async () => {
    apiClient.login.mockResolvedValueOnce({
      access_token: "tok",
      user: { id: 1, email: "user@test.com" },
    });
    apiClient.logout.mockRejectedValueOnce(new Error("Network error"));

    let authRef = {};
    renderWithAuth(
      <AuthConsumer
        onRender={(v) => {
          authRef = v;
        }}
      />,
    );

    await act(async () => {
      await authRef.login({ email: "user@test.com", password: "pass" });
    });
    await act(async () => {
      await authRef.logout();
    });

    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(apiClient.setToken).toHaveBeenLastCalledWith(null);
  });

  it("register sets authenticated state", async () => {
    apiClient.register.mockResolvedValueOnce({
      access_token: "reg-token",
      user: { id: 3, email: "new@test.com", first_name: "New" },
    });

    let authRef = {};
    renderWithAuth(
      <AuthConsumer
        onRender={(v) => {
          authRef = v;
        }}
      />,
    );

    await act(async () => {
      await authRef.register({
        email: "new@test.com",
        password: "securepass",
        first_name: "New",
        last_name: "User",
        business_name: "Test Co",
      });
    });

    expect(screen.getByTestId("authenticated").textContent).toBe("true");
  });

  it("clearError removes error from state", async () => {
    apiClient.login.mockRejectedValueOnce(new Error("Bad creds"));

    let authRef = {};
    renderWithAuth(
      <AuthConsumer
        onRender={(v) => {
          authRef = v;
        }}
      />,
    );

    await act(async () => {
      try {
        await authRef.login({ email: "x", password: "y" });
      } catch {}
    });
    expect(screen.getByTestId("error").textContent).not.toBe("");

    act(() => authRef.clearError());
    expect(screen.getByTestId("error").textContent).toBe("");
  });

  it("updateUser merges new fields into user state", async () => {
    apiClient.login.mockResolvedValueOnce({
      access_token: "tok",
      user: { id: 1, email: "u@test.com", first_name: "Old" },
    });

    let authRef = {};
    renderWithAuth(
      <AuthConsumer
        onRender={(v) => {
          authRef = v;
        }}
      />,
    );
    await act(async () => {
      await authRef.login({ email: "u@test.com", password: "p" });
    });

    act(() => authRef.updateUser({ first_name: "Updated" }));
    // State should merge - email should remain
    expect(screen.getByTestId("user").textContent).toBe("u@test.com");
  });
});

describe("AppContext", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("starts with default light theme", () => {
    let appRef = {};
    render(
      <AppProvider>
        <AppConsumer
          onRender={(v) => {
            appRef = v;
          }}
        />
      </AppProvider>,
    );
    expect(screen.getByTestId("theme").textContent).toBe("light");
  });

  it("setTheme updates theme and persists to localStorage", () => {
    let appRef = {};
    render(
      <AppProvider>
        <AppConsumer
          onRender={(v) => {
            appRef = v;
          }}
        />
      </AppProvider>,
    );

    act(() => appRef.setTheme("dark"));
    expect(screen.getByTestId("theme").textContent).toBe("dark");
    expect(localStorage.getItem("nexafi_theme")).toBe("dark");
  });

  it("restores theme from localStorage on mount", () => {
    localStorage.setItem("nexafi_theme", "dark");
    render(
      <AppProvider>
        <AppConsumer onRender={() => {}} />
      </AppProvider>,
    );
    expect(screen.getByTestId("theme").textContent).toBe("dark");
  });

  it("addNotification appends to notifications list", () => {
    let appRef = {};
    render(
      <AppProvider>
        <AppConsumer
          onRender={(v) => {
            appRef = v;
          }}
        />
      </AppProvider>,
    );

    expect(screen.getByTestId("notifications").textContent).toBe("0");
    act(() =>
      appRef.addNotification({ type: "info", title: "Test", message: "Hello" }),
    );
    expect(screen.getByTestId("notifications").textContent).toBe("1");
  });

  it("removeNotification removes correct notification", () => {
    let appRef = {};
    render(
      <AppProvider>
        <AppConsumer
          onRender={(v) => {
            appRef = v;
          }}
        />
      </AppProvider>,
    );

    let notifId;
    act(() => {
      appRef.addNotification({ type: "info", title: "T", message: "M" });
    });

    // Get the id from context
    act(() => {
      // notifications[0].id was set as Date.now().toString() in addNotification
      const id = appRef.notifications[0]?.id;
      if (id) appRef.removeNotification(id);
    });

    expect(screen.getByTestId("notifications").textContent).toBe("0");
  });

  it("useAuth throws outside AuthProvider", () => {
    const BadComponent = () => {
      useAuth();
      return null;
    };
    expect(() => render(<BadComponent />)).toThrow(
      "useAuth must be used within an AuthProvider",
    );
  });

  it("useApp throws outside AppProvider", () => {
    const BadComponent = () => {
      useApp();
      return null;
    };
    expect(() => render(<BadComponent />)).toThrow(
      "useApp must be used within an AppProvider",
    );
  });
});
