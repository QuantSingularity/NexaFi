import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MobileLayout from "../components/MobileLayout";
import { MobileProviders } from "../contexts/MobileContext";
import mobileApiClient from "../lib/mobileApi";

vi.mock("../lib/mobileApi");

const mockUser = {
  first_name: "Jane",
  last_name: "Doe",
  email: "jane@example.com",
  business_name: "Acme Corp",
};

const renderLayout = (initialPath = "/dashboard") =>
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <MobileProviders>
        <MobileLayout>
          <div>Page Content</div>
        </MobileLayout>
      </MobileProviders>
    </MemoryRouter>,
  );

describe("MobileLayout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.getItem.mockReturnValue(null);
    mobileApiClient.getProfile = vi.fn().mockResolvedValue(mockUser);
    mobileApiClient.setToken = vi.fn();
    mobileApiClient.clearCache = vi.fn();
    mobileApiClient.logout = vi.fn().mockResolvedValue(undefined);
  });

  it("renders children content", () => {
    renderLayout();
    expect(screen.getByText("Page Content")).toBeInTheDocument();
  });

  it("renders mobile header with menu button", () => {
    renderLayout();
    expect(screen.getByRole("button", { name: "" })).toBeInTheDocument();
  });

  it("shows page title based on route", () => {
    renderLayout("/dashboard");
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("opens sidebar when menu button clicked", async () => {
    const user = userEvent.setup();
    renderLayout();

    const menuButton = screen.getAllByRole("button")[0];
    await user.click(menuButton);

    await waitFor(() => {
      expect(screen.getByText("NexaFi Mobile")).toBeInTheDocument();
    });
  });

  it("closes sidebar when backdrop clicked", async () => {
    const user = userEvent.setup();
    renderLayout();

    const menuButton = screen.getAllByRole("button")[0];
    await user.click(menuButton);

    await waitFor(() => {
      expect(screen.getByText("NexaFi Mobile")).toBeInTheDocument();
    });

    const backdrop = document.querySelector(".fixed.inset-0.bg-black\\/50");
    if (backdrop) {
      await user.click(backdrop);
      await waitFor(() => {
        expect(screen.queryByText("Sign Out")).not.toBeInTheDocument();
      });
    }
  });

  it("renders bottom navigation tabs", () => {
    renderLayout();
    expect(screen.getByText("Accounting")).toBeInTheDocument();
    expect(screen.getByText("Payments")).toBeInTheDocument();
  });
});
