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
  balance: 50000,
  income: 25000,
  expenses: 15000,
  transactions: [
    {
      id: 1,
      description: "Salary",
      amount: 5000,
      type: "income",
      date: "2025-01-15",
    },
    {
      id: 2,
      description: "Rent",
      amount: -1500,
      type: "expense",
      date: "2025-01-10",
    },
  ],
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

    expect(screen.getByRole("status")).toBeInTheDocument(); // Loading spinner
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

    const refreshButton = screen.getByRole("button", { name: /refresh/i });
    await user.click(refreshButton);

    expect(mobileApiClient.getDashboardData).toHaveBeenCalledTimes(2);
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
});
