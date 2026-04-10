import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MobileAccountingModule from "../components/MobileAccountingModule";
import { MobileProviders } from "../contexts/MobileContext";
import mobileApiClient from "../lib/mobileApi";

vi.mock("../lib/mobileApi");

const wrapper = ({ children }) => (
  <BrowserRouter>
    <MobileProviders>{children}</MobileProviders>
  </BrowserRouter>
);

describe("MobileAccountingModule", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.getItem.mockReturnValue(null);
    mobileApiClient.getProfile = vi.fn();
    mobileApiClient.getAccounts = vi.fn().mockResolvedValue([]);
    mobileApiClient.getJournalEntries = vi.fn().mockResolvedValue([]);
  });

  it("renders without crashing", () => {
    render(<MobileAccountingModule />, { wrapper });
    expect(screen.getByText(/Accounting/i)).toBeInTheDocument();
  });

  it("renders tab navigation", () => {
    render(<MobileAccountingModule />, { wrapper });
    expect(screen.getByRole("tab", { name: /overview/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /accounts/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /journal/i })).toBeInTheDocument();
  });

  it("shows accounts list", async () => {
    render(<MobileAccountingModule />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText(/Cash/i)).toBeInTheDocument();
    });
  });

  it("filters accounts by search query", async () => {
    const user = userEvent.setup();
    render(<MobileAccountingModule />, { wrapper });

    const searchInput = screen.getByPlaceholderText(/search/i);
    await user.type(searchInput, "Cash");

    await waitFor(() => {
      expect(screen.getByText("Cash")).toBeInTheDocument();
    });
  });

  it("switches to Accounts tab", async () => {
    const user = userEvent.setup();
    render(<MobileAccountingModule />, { wrapper });

    await user.click(screen.getByRole("tab", { name: /accounts/i }));

    await waitFor(() => {
      expect(
        screen.getAllByText(/Asset|Liability|Equity/).length,
      ).toBeGreaterThan(0);
    });
  });

  it("switches to Journal tab", async () => {
    const user = userEvent.setup();
    render(<MobileAccountingModule />, { wrapper });

    await user.click(screen.getByRole("tab", { name: /journal/i }));

    await waitFor(() => {
      expect(screen.getByText(/journal entries/i)).toBeInTheDocument();
    });
  });
});
