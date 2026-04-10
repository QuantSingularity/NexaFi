import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MobileDashboard from "../components/MobileDashboard";
import { MobileProviders } from "../contexts/MobileContext";
import mobileApiClient from "../lib/mobileApi";

vi.mock("../lib/mobileApi");

const wrapper = ({ children }) => (
  <BrowserRouter>
    <MobileProviders>{children}</MobileProviders>
  </BrowserRouter>
);

const mockDashboardData = {
  totalBalance: 50000,
  monthlyIncome: 25000,
  monthlyExpenses: 15000,
  cashFlow: 10000,
  accounts: 3,
  transactions: 10,
  pendingPayments: 2,
};

describe("MobileDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mobileApiClient.getDashboardData = vi
      .fn()
      .mockResolvedValue(mockDashboardData);
  });

  it("renders dashboard with loading state initially", () => {
    render(<MobileDashboard />, { wrapper });
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("displays financial summary after loading", async () => {
    render(<MobileDashboard />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/Total Balance/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/\$50,000/)).toBeInTheDocument();
  });

  it("toggles balance visibility", async () => {
    const user = userEvent.setup();
    render(<MobileDashboard />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/\$50,000/)).toBeInTheDocument();
    });

    const eyeButton = screen.getByLabelText(/toggle balance visibility/i);
    await user.click(eyeButton);

    expect(screen.getByText(/••••••/)).toBeInTheDocument();
    expect(screen.queryByText(/\$50,000/)).not.toBeInTheDocument();
  });

  it("refreshes data when refresh button clicked", async () => {
    const user = userEvent.setup();
    render(<MobileDashboard />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/Total Balance/i)).toBeInTheDocument();
    });

    const refreshButton = screen.getByRole("button", {
      name: /refresh dashboard/i,
    });
    await user.click(refreshButton);

    await waitFor(() => {
      expect(mobileApiClient.getDashboardData).toHaveBeenCalledTimes(2);
    });
  });

  it("handles API errors gracefully", async () => {
    mobileApiClient.getDashboardData = vi
      .fn()
      .mockRejectedValue(new Error("API Error"));

    render(<MobileDashboard />, { wrapper });

    await waitFor(() => {
      expect(
        screen.getByText(/failed to load dashboard data/i),
      ).toBeInTheDocument();
    });
  });

  it("shows income and expense stats", async () => {
    render(<MobileDashboard />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/Income/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/\$25,000/)).toBeInTheDocument();
    expect(screen.getByText(/Expenses/i)).toBeInTheDocument();
  });

  it("shows quick actions", async () => {
    render(<MobileDashboard />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/Quick Actions/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Add Transaction/i)).toBeInTheDocument();
    expect(screen.getByText(/Make Payment/i)).toBeInTheDocument();
  });
});
