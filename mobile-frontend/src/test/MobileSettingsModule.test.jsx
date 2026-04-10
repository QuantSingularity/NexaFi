import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MobileSettingsModule from "../components/MobileSettingsModule";
import { MobileProviders } from "../contexts/MobileContext";
import mobileApiClient from "../lib/mobileApi";

vi.mock("../lib/mobileApi");

const mockUser = {
  first_name: "Jane",
  last_name: "Doe",
  email: "jane@example.com",
  phone: "+1234567890",
  company: "Acme",
};

const wrapper = ({ children }) => (
  <BrowserRouter>
    <MobileProviders>{children}</MobileProviders>
  </BrowserRouter>
);

describe("MobileSettingsModule", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.getItem.mockReturnValue(null);
    mobileApiClient.getProfile = vi.fn().mockResolvedValue(mockUser);
    mobileApiClient.updateProfile = vi.fn().mockResolvedValue(mockUser);
    mobileApiClient.setToken = vi.fn();
    mobileApiClient.clearCache = vi.fn();
    mobileApiClient.logout = vi.fn().mockResolvedValue(undefined);
  });

  it("renders settings module", async () => {
    render(<MobileSettingsModule />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText(/Settings/i)).toBeInTheDocument();
    });
  });

  it("shows tab navigation", async () => {
    render(<MobileSettingsModule />, { wrapper });
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /profile/i })).toBeInTheDocument();
      expect(
        screen.getByRole("tab", { name: /security/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("tab", { name: /preferences/i }),
      ).toBeInTheDocument();
    });
  });

  it("shows notifications tab", async () => {
    render(<MobileSettingsModule />, { wrapper });
    await waitFor(() => {
      expect(
        screen.getByRole("tab", { name: /notifications/i }),
      ).toBeInTheDocument();
    });
  });

  it("shows logout button", async () => {
    render(<MobileSettingsModule />, { wrapper });
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /log out/i }),
      ).toBeInTheDocument();
    });
  });

  it("opens logout confirmation dialog", async () => {
    const user = userEvent.setup();
    render(<MobileSettingsModule />, { wrapper });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /log out/i }),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /log out/i }));

    await waitFor(() => {
      expect(screen.getByText(/Confirm Logout/i)).toBeInTheDocument();
    });
  });

  it("cancels logout when Cancel is clicked", async () => {
    const user = userEvent.setup();
    render(<MobileSettingsModule />, { wrapper });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /log out/i }),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /log out/i }));

    await waitFor(() => {
      expect(screen.getByText(/Confirm Logout/i)).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /cancel/i }));

    await waitFor(() => {
      expect(screen.queryByText(/Confirm Logout/i)).not.toBeInTheDocument();
    });
  });

  it("toggles dark mode switch", async () => {
    const user = userEvent.setup();
    render(<MobileSettingsModule />, { wrapper });

    await user.click(screen.getByRole("tab", { name: /preferences/i }));

    await waitFor(() => {
      expect(screen.getByText(/Dark Mode/i)).toBeInTheDocument();
    });

    const darkModeSwitch = screen.getByRole("switch");
    await user.click(darkModeSwitch);
    expect(localStorage.setItem).toHaveBeenCalledWith("theme", "dark");
  });
});
