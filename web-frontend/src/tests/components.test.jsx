import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter, MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import AuthPage from "../components/AuthPage";
import Dashboard from "../components/Dashboard";
import Layout from "../components/Layout";
import Homepage from "../components/Homepage";
import DocumentsModule from "../components/DocumentsModule";

// ── Shared Mocks ─────────────────────────────────────────────────────────────

vi.mock("../lib/api", () => ({
  default: {
    getAccounts: vi.fn().mockResolvedValue({ accounts: [] }),
    getJournalEntries: vi.fn().mockResolvedValue({ journal_entries: [] }),
    getTrialBalance: vi.fn().mockResolvedValue({
      total_debits: 0,
      total_credits: 0,
      is_balanced: true,
    }),
    getDocuments: vi.fn().mockResolvedValue({ documents: [] }),
    getDocumentTemplates: vi.fn().mockResolvedValue({ templates: [] }),
    getInsights: vi.fn().mockResolvedValue({ insights: [] }),
    getChatSessions: vi.fn().mockResolvedValue({ sessions: [] }),
    getPaymentMethods: vi.fn().mockResolvedValue({ payment_methods: [] }),
    getTransactions: vi.fn().mockResolvedValue({ transactions: [] }),
    getWallets: vi.fn().mockResolvedValue({ wallets: [] }),
    getPaymentAnalytics: vi.fn().mockResolvedValue({}),
  },
}));

const mockUseAuth = vi.fn(() => ({
  isAuthenticated: true,
  loading: false,
  user: {
    first_name: "Jane",
    last_name: "Doe",
    email: "jane@test.com",
    business_name: "Acme Ltd",
  },
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  error: null,
  clearError: vi.fn(),
}));

const mockUseApp = vi.fn(() => ({
  addNotification: vi.fn(),
  theme: "light",
  setTheme: vi.fn(),
  sidebarOpen: true,
  setSidebarOpen: vi.fn(),
  notifications: [],
  removeNotification: vi.fn(),
}));

vi.mock("../contexts/AppContext", () => ({
  useAuth: () => mockUseAuth(),
  useApp: () => mockUseApp(),
  AuthProvider: ({ children }) => <>{children}</>,
  AppProvider: ({ children }) => <>{children}</>,
}));

// ── AuthPage ──────────────────────────────────────────────────────────────────

describe("AuthPage", () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({
      login: vi.fn(),
      register: vi.fn(),
      loading: false,
      error: null,
      clearError: vi.fn(),
    });
  });

  it("renders login tab by default", () => {
    render(<AuthPage />);
    expect(screen.getByText("Sign In")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/enter your email/i),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/enter your password/i),
    ).toBeInTheDocument();
  });

  it("shows NexaFi branding", () => {
    render(<AuthPage />);
    const nexafiElements = screen.getAllByText("NexaFi");
    expect(nexafiElements.length).toBeGreaterThan(0);
  });

  it("switches to register tab when Sign Up clicked", async () => {
    render(<AuthPage />);
    await userEvent.click(screen.getByText("Sign Up"));
    expect(screen.getByPlaceholderText(/first name/i)).toBeInTheDocument();
  });

  it("shows password mismatch error on register", async () => {
    render(<AuthPage />);
    await userEvent.click(screen.getByText("Sign Up"));

    await userEvent.type(screen.getByPlaceholderText(/first name/i), "John");
    await userEvent.type(screen.getByPlaceholderText(/last name/i), "Doe");
    await userEvent.type(
      screen.getByPlaceholderText(/your business name/i),
      "Test Co",
    );
    await userEvent.type(
      screen.getByPlaceholderText(/enter your email/i),
      "j@test.com",
    );
    await userEvent.type(
      screen.getByPlaceholderText(/create a password/i),
      "password123",
    );
    await userEvent.type(
      screen.getByPlaceholderText(/confirm your password/i),
      "different123",
    );

    await userEvent.click(screen.getByText("Create Account"));
    expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
  });

  it("shows minimum password length error on register", async () => {
    render(<AuthPage />);
    await userEvent.click(screen.getByText("Sign Up"));

    await userEvent.type(screen.getByPlaceholderText(/first name/i), "John");
    await userEvent.type(screen.getByPlaceholderText(/last name/i), "Doe");
    await userEvent.type(
      screen.getByPlaceholderText(/your business name/i),
      "Test Co",
    );
    await userEvent.type(
      screen.getByPlaceholderText(/enter your email/i),
      "j@test.com",
    );
    await userEvent.type(
      screen.getByPlaceholderText(/create a password/i),
      "short",
    );
    await userEvent.type(
      screen.getByPlaceholderText(/confirm your password/i),
      "short",
    );

    await userEvent.click(screen.getByText("Create Account"));
    expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
  });

  it("toggles password visibility", async () => {
    render(<AuthPage />);
    const passwordInput = screen.getByPlaceholderText(/enter your password/i);
    expect(passwordInput).toHaveAttribute("type", "password");

    const toggleButtons = screen.getAllByRole("button", { name: "" });
    const eyeButton = toggleButtons.find((b) => b.querySelector("svg"));
    if (eyeButton) {
      await userEvent.click(eyeButton);
      expect(passwordInput).toHaveAttribute("type", "text");
    }
  });

  it("shows server error when login fails", () => {
    mockUseAuth.mockReturnValue({
      login: vi.fn(),
      register: vi.fn(),
      loading: false,
      error: "Invalid credentials",
      clearError: vi.fn(),
    });
    render(<AuthPage />);
    expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
  });

  it("shows loading state during submit", () => {
    mockUseAuth.mockReturnValue({
      login: vi.fn(),
      register: vi.fn(),
      loading: true,
      error: null,
      clearError: vi.fn(),
    });
    render(<AuthPage />);
    expect(screen.getByText(/signing in/i)).toBeInTheDocument();
  });

  it("calls login with email and password on submit", async () => {
    const loginMock = vi.fn().mockResolvedValue({});
    mockUseAuth.mockReturnValue({
      login: loginMock,
      register: vi.fn(),
      loading: false,
      error: null,
      clearError: vi.fn(),
    });

    render(<AuthPage />);
    await userEvent.type(
      screen.getByPlaceholderText(/enter your email/i),
      "user@test.com",
    );
    await userEvent.type(
      screen.getByPlaceholderText(/enter your password/i),
      "mypassword",
    );
    await userEvent.click(screen.getByText("Sign In"));

    await waitFor(() => {
      expect(loginMock).toHaveBeenCalledWith({
        email: "user@test.com",
        password: "mypassword",
      });
    });
  });
});

// ── Dashboard ─────────────────────────────────────────────────────────────────

describe("Dashboard", () => {
  it("renders loading skeleton initially", () => {
    render(<Dashboard />);
    // animate-pulse elements should be present during loading
    const pulseElements = document.querySelectorAll(".animate-pulse");
    expect(pulseElements.length).toBeGreaterThan(0);
  });

  it("renders welcome message with user name after load", async () => {
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText(/welcome back, jane/i)).toBeInTheDocument();
    });
  });

  it("renders business name in subtitle", async () => {
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText(/acme ltd/i)).toBeInTheDocument();
    });
  });

  it("renders key metric cards", async () => {
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("Total Revenue")).toBeInTheDocument();
      expect(screen.getByText("Total Expenses")).toBeInTheDocument();
      expect(screen.getByText("Net Income")).toBeInTheDocument();
    });
  });

  it("renders cash flow chart section", async () => {
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("Cash Flow Trend")).toBeInTheDocument();
    });
  });

  it("renders expense breakdown section", async () => {
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("Expense Breakdown")).toBeInTheDocument();
    });
  });

  it("renders AI insights section", async () => {
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("AI Insights")).toBeInTheDocument();
    });
  });

  it("renders recent transactions section", async () => {
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText("Recent Transactions")).toBeInTheDocument();
    });
  });
});

// ── Layout ────────────────────────────────────────────────────────────────────

describe("Layout", () => {
  const renderLayout = () =>
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Layout>
          <div data-testid="child-content">Child</div>
        </Layout>
      </MemoryRouter>,
    );

  it("renders sidebar with navigation items", () => {
    renderLayout();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Accounting")).toBeInTheDocument();
    expect(screen.getByText("Payments")).toBeInTheDocument();
    expect(screen.getByText("AI Insights")).toBeInTheDocument();
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("renders NexaFi brand in sidebar", () => {
    renderLayout();
    const brandElements = screen.getAllByText("NexaFi");
    expect(brandElements.length).toBeGreaterThan(0);
  });

  it("renders children content", () => {
    renderLayout();
    expect(screen.getByTestId("child-content")).toBeInTheDocument();
  });

  it("renders search input in header", () => {
    renderLayout();
    expect(
      screen.getByPlaceholderText(/search transactions/i),
    ).toBeInTheDocument();
  });

  it("renders user name in header", () => {
    renderLayout();
    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
  });

  it("renders business name in header", () => {
    renderLayout();
    expect(screen.getByText("Acme Ltd")).toBeInTheDocument();
  });

  it("highlights Dashboard as active on /dashboard route", () => {
    renderLayout();
    // The active button has a specific class
    const dashboardButtons = screen.getAllByText("Dashboard");
    const navButton = dashboardButtons.find((el) =>
      el.closest("button")?.className?.includes("text-blue-700"),
    );
    expect(navButton).toBeTruthy();
  });

  it("shows empty notifications count when none", () => {
    renderLayout();
    // Bell button should not show badge when notifications is []
    const badge = document.querySelector(".bg-red-500");
    expect(badge).toBeNull();
  });

  it("shows notification count badge when notifications exist", () => {
    mockUseApp.mockReturnValue({
      addNotification: vi.fn(),
      theme: "light",
      setTheme: vi.fn(),
      sidebarOpen: true,
      setSidebarOpen: vi.fn(),
      notifications: [{ id: "1", title: "Alert", message: "Test" }],
      removeNotification: vi.fn(),
    });
    renderLayout();
    expect(screen.getByText("1")).toBeInTheDocument();
  });
});

// ── Homepage ──────────────────────────────────────────────────────────────────

describe("Homepage", () => {
  it("renders NexaFi brand name", () => {
    render(
      <BrowserRouter>
        <Homepage />
      </BrowserRouter>,
    );
    const elements = screen.getAllByText("NexaFi");
    expect(elements.length).toBeGreaterThan(0);
  });

  it("renders hero headline", () => {
    render(
      <BrowserRouter>
        <Homepage />
      </BrowserRouter>,
    );
    expect(screen.getByText(/future of/i)).toBeInTheDocument();
  });

  it("has Get Started CTA buttons", () => {
    render(
      <BrowserRouter>
        <Homepage />
      </BrowserRouter>,
    );
    const ctaButtons = screen.getAllByText(/get started/i);
    expect(ctaButtons.length).toBeGreaterThan(0);
  });

  it("renders features section", () => {
    render(
      <BrowserRouter>
        <Homepage />
      </BrowserRouter>,
    );
    expect(screen.getByText(/AI-Powered Insights/i)).toBeInTheDocument();
    expect(screen.getByText(/Advanced Analytics/i)).toBeInTheDocument();
  });

  it("renders testimonials section", () => {
    render(
      <BrowserRouter>
        <Homepage />
      </BrowserRouter>,
    );
    expect(screen.getByText(/Sarah Johnson/i)).toBeInTheDocument();
  });
});

// ── DocumentsModule ───────────────────────────────────────────────────────────

describe("DocumentsModule", () => {
  it("renders loading skeleton initially", () => {
    render(<DocumentsModule />);
    const pulseElements = document.querySelectorAll(".animate-pulse");
    expect(pulseElements.length).toBeGreaterThan(0);
  });

  it("renders Documents heading after load", async () => {
    render(<DocumentsModule />);
    await waitFor(() => {
      expect(screen.getByText("Documents")).toBeInTheDocument();
    });
  });

  it("renders stats cards", async () => {
    render(<DocumentsModule />);
    await waitFor(() => {
      expect(screen.getByText("Total Documents")).toBeInTheDocument();
      expect(screen.getByText("Templates")).toBeInTheDocument();
      expect(screen.getByText("Shared")).toBeInTheDocument();
    });
  });

  it("renders upload button", async () => {
    render(<DocumentsModule />);
    await waitFor(() => {
      expect(screen.getByText(/upload document/i)).toBeInTheDocument();
    });
  });

  it("renders Templates tab", async () => {
    render(<DocumentsModule />);
    await waitFor(() => {
      expect(screen.getByText("Templates")).toBeInTheDocument();
    });
  });

  it("shows empty state when no documents", async () => {
    render(<DocumentsModule />);
    await waitFor(() => {
      expect(screen.getByText(/no documents found/i)).toBeInTheDocument();
    });
  });

  it("opens upload dialog when upload button is clicked", async () => {
    render(<DocumentsModule />);
    await waitFor(() => screen.getByText(/upload document/i));
    await userEvent.click(screen.getByText(/upload document/i));
    expect(screen.getByText(/drop your file here/i)).toBeInTheDocument();
  });
});
