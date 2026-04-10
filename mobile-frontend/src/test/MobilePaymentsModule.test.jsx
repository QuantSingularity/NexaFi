import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MobilePaymentsModule from "../components/MobilePaymentsModule";
import { MobileProviders } from "../contexts/MobileContext";
import mobileApiClient from "../lib/mobileApi";

vi.mock("../lib/mobileApi");

const wrapper = ({ children }) => (
  <BrowserRouter>
    <MobileProviders>{children}</MobileProviders>
  </BrowserRouter>
);

describe("MobilePaymentsModule", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.getItem.mockReturnValue(null);
    mobileApiClient.getProfile = vi.fn();
    mobileApiClient.getTransactions = vi
      .fn()
      .mockResolvedValue({ transactions: [] });
    mobileApiClient.getPaymentMethods = vi
      .fn()
      .mockResolvedValue({ methods: [] });
    mobileApiClient.getWallets = vi.fn().mockResolvedValue({ wallets: [] });
    mobileApiClient.createTransaction = vi
      .fn()
      .mockResolvedValue({ id: "tx1" });
    mobileApiClient.addPaymentMethod = vi.fn().mockResolvedValue({ id: "m1" });
  });

  it("renders without crashing", async () => {
    render(<MobilePaymentsModule />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText(/Payments/i)).toBeInTheDocument();
    });
  });

  it("shows tab navigation", async () => {
    render(<MobilePaymentsModule />, { wrapper });
    await waitFor(() => {
      expect(
        screen.getByRole("tab", { name: /transactions/i }),
      ).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /methods/i })).toBeInTheDocument();
    });
  });

  it("shows empty state when no transactions", async () => {
    render(<MobilePaymentsModule />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText(/No transactions/i)).toBeInTheDocument();
    });
  });

  it("opens new payment dialog", async () => {
    const user = userEvent.setup();
    render(<MobilePaymentsModule />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/Send Money/i)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/Send Money/i));

    await waitFor(() => {
      expect(screen.getByText(/New Payment/i)).toBeInTheDocument();
    });
  });

  it("switches to payment methods tab", async () => {
    const user = userEvent.setup();
    render(<MobilePaymentsModule />, { wrapper });

    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /methods/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("tab", { name: /methods/i }));

    await waitFor(() => {
      expect(screen.getByText(/Add Payment Method/i)).toBeInTheDocument();
    });
  });

  it("shows balance toggle button", async () => {
    render(<MobilePaymentsModule />, { wrapper });
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /toggle.*balance/i }),
      ).toBeInTheDocument();
    });
  });
});
