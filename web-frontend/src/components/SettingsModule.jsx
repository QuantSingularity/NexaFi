import {
  Bell,
  Building,
  Eye,
  EyeOff,
  Globe,
  Key,
  Palette,
  Shield,
  User,
} from "lucide-react";
import { useState } from "react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useApp, useAuth } from "../contexts/AppContext";
import apiClient from "../lib/api";

const SettingsModule = () => {
  const { user, updateUser } = useAuth();
  const { theme, setTheme, addNotification } = useApp();
  const [activeTab, setActiveTab] = useState("profile");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const [profileData, setProfileData] = useState({
    first_name: user?.first_name || "",
    last_name: user?.last_name || "",
    email: user?.email || "",
    phone: user?.phone || "",
    business_name: user?.business_name || "",
    business_address: user?.business_address || "",
    business_phone: user?.business_phone || "",
    business_website: user?.business_website || "",
    business_description: user?.business_description || "",
  });

  const [securityData, setSecurityData] = useState({
    current_password: "",
    new_password: "",
    confirm_password: "",
  });

  const [notificationSettings, setNotificationSettings] = useState({
    email_notifications: true,
    push_notifications: true,
    sms_notifications: false,
    marketing_emails: false,
    security_alerts: true,
    payment_notifications: true,
    ai_insights: true,
  });

  const handleProfileSave = async () => {
    setLoading(true);
    try {
      await apiClient.updateUserProfile(profileData);
      updateUser(profileData);
      addNotification({
        type: "success",
        title: "Success",
        message: "Profile updated successfully",
      });
    } catch (_error) {
      addNotification({
        type: "error",
        title: "Error",
        message: "Failed to update profile",
      });
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordChange = async () => {
    if (securityData.new_password !== securityData.confirm_password) {
      addNotification({
        type: "error",
        title: "Error",
        message: "Passwords do not match",
      });
      return;
    }

    if (securityData.new_password.length < 8) {
      addNotification({
        type: "error",
        title: "Error",
        message: "Password must be at least 8 characters",
      });
      return;
    }

    setLoading(true);
    try {
      await apiClient.updateUserProfile({
        current_password: securityData.current_password,
        new_password: securityData.new_password,
      });
      addNotification({
        type: "success",
        title: "Success",
        message: "Password updated successfully",
      });
      setSecurityData({
        current_password: "",
        new_password: "",
        confirm_password: "",
      });
    } catch (_error) {
      addNotification({
        type: "error",
        title: "Error",
        message: "Failed to update password",
      });
    } finally {
      setLoading(false);
    }
  };

  const ProfileTab = () => (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <User className="w-5 h-5" />
            <span>Personal Information</span>
          </CardTitle>
          <CardDescription>
            Update your personal details and contact information
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center space-x-6">
            <Avatar className="w-20 h-20">
              <AvatarImage src={user?.avatar} />
              <AvatarFallback className="text-lg">
                {user?.first_name?.[0]}
                {user?.last_name?.[0]}
              </AvatarFallback>
            </Avatar>
            <div>
              <Button variant="outline">Change Photo</Button>
              <p className="text-sm text-gray-500 mt-2">
                JPG, GIF or PNG. 1MB max.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <Label htmlFor="first_name">First Name</Label>
              <Input
                id="first_name"
                value={profileData.first_name}
                onChange={(e) =>
                  setProfileData((prev) => ({
                    ...prev,
                    first_name: e.target.value,
                  }))
                }
                placeholder="Enter your first name"
              />
            </div>
            <div>
              <Label htmlFor="last_name">Last Name</Label>
              <Input
                id="last_name"
                value={profileData.last_name}
                onChange={(e) =>
                  setProfileData((prev) => ({
                    ...prev,
                    last_name: e.target.value,
                  }))
                }
                placeholder="Enter your last name"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <Label htmlFor="email">Email Address</Label>
              <Input
                id="email"
                type="email"
                value={profileData.email}
                onChange={(e) =>
                  setProfileData((prev) => ({ ...prev, email: e.target.value }))
                }
                placeholder="Enter your email"
              />
            </div>
            <div>
              <Label htmlFor="phone">Phone Number</Label>
              <Input
                id="phone"
                value={profileData.phone}
                onChange={(e) =>
                  setProfileData((prev) => ({ ...prev, phone: e.target.value }))
                }
                placeholder="Enter your phone number"
              />
            </div>
          </div>

          <Button onClick={handleProfileSave} disabled={loading}>
            {loading ? "Saving..." : "Save Changes"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Building className="w-5 h-5" />
            <span>Business Information</span>
          </CardTitle>
          <CardDescription>
            Manage your business details and settings
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <Label htmlFor="business_name">Business Name</Label>
            <Input
              id="business_name"
              value={profileData.business_name}
              onChange={(e) =>
                setProfileData((prev) => ({
                  ...prev,
                  business_name: e.target.value,
                }))
              }
              placeholder="Enter your business name"
            />
          </div>

          <div>
            <Label htmlFor="business_address">Business Address</Label>
            <Textarea
              id="business_address"
              value={profileData.business_address}
              onChange={(e) =>
                setProfileData((prev) => ({
                  ...prev,
                  business_address: e.target.value,
                }))
              }
              placeholder="Enter your business address"
              rows={3}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <Label htmlFor="business_phone">Business Phone</Label>
              <Input
                id="business_phone"
                value={profileData.business_phone}
                onChange={(e) =>
                  setProfileData((prev) => ({
                    ...prev,
                    business_phone: e.target.value,
                  }))
                }
                placeholder="Enter business phone"
              />
            </div>
            <div>
              <Label htmlFor="business_website">Website</Label>
              <Input
                id="business_website"
                value={profileData.business_website}
                onChange={(e) =>
                  setProfileData((prev) => ({
                    ...prev,
                    business_website: e.target.value,
                  }))
                }
                placeholder="https://yourwebsite.com"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="business_description">Business Description</Label>
            <Textarea
              id="business_description"
              value={profileData.business_description}
              onChange={(e) =>
                setProfileData((prev) => ({
                  ...prev,
                  business_description: e.target.value,
                }))
              }
              placeholder="Describe your business"
              rows={4}
            />
          </div>

          <Button onClick={handleProfileSave} disabled={loading}>
            {loading ? "Saving..." : "Save Business Info"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );

  const SecurityTab = () => (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Key className="w-5 h-5" />
            <span>Change Password</span>
          </CardTitle>
          <CardDescription>
            Update your password to keep your account secure
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <Label htmlFor="current_password">Current Password</Label>
            <div className="relative">
              <Input
                id="current_password"
                type={showPassword ? "text" : "password"}
                value={securityData.current_password}
                onChange={(e) =>
                  setSecurityData((prev) => ({
                    ...prev,
                    current_password: e.target.value,
                  }))
                }
                placeholder="Enter current password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          <div>
            <Label htmlFor="new_password">New Password</Label>
            <Input
              id="new_password"
              type="password"
              value={securityData.new_password}
              onChange={(e) =>
                setSecurityData((prev) => ({
                  ...prev,
                  new_password: e.target.value,
                }))
              }
              placeholder="Enter new password"
            />
          </div>

          <div>
            <Label htmlFor="confirm_password">Confirm New Password</Label>
            <Input
              id="confirm_password"
              type="password"
              value={securityData.confirm_password}
              onChange={(e) =>
                setSecurityData((prev) => ({
                  ...prev,
                  confirm_password: e.target.value,
                }))
              }
              placeholder="Confirm new password"
            />
          </div>

          <Button onClick={handlePasswordChange} disabled={loading}>
            {loading ? "Updating..." : "Update Password"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Shield className="w-5 h-5" />
            <span>Two-Factor Authentication</span>
          </CardTitle>
          <CardDescription>
            Add an extra layer of security to your account
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">SMS Authentication</p>
              <p className="text-sm text-gray-500">Receive codes via SMS</p>
            </div>
            <Switch />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Authenticator App</p>
              <p className="text-sm text-gray-500">
                Use Google Authenticator or similar
              </p>
            </div>
            <Switch />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Email Verification</p>
              <p className="text-sm text-gray-500">
                Verify login attempts via email
              </p>
            </div>
            <Switch defaultChecked />
          </div>
        </CardContent>
      </Card>
    </div>
  );

  const NotificationsTab = () => (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Bell className="w-5 h-5" />
            <span>Notification Preferences</span>
          </CardTitle>
          <CardDescription>
            Choose how you want to be notified about important events
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Email Notifications</p>
                <p className="text-sm text-gray-500">
                  Receive notifications via email
                </p>
              </div>
              <Switch
                checked={notificationSettings.email_notifications}
                onCheckedChange={(checked) =>
                  setNotificationSettings((prev) => ({
                    ...prev,
                    email_notifications: checked,
                  }))
                }
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Push Notifications</p>
                <p className="text-sm text-gray-500">
                  Receive browser push notifications
                </p>
              </div>
              <Switch
                checked={notificationSettings.push_notifications}
                onCheckedChange={(checked) =>
                  setNotificationSettings((prev) => ({
                    ...prev,
                    push_notifications: checked,
                  }))
                }
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">SMS Notifications</p>
                <p className="text-sm text-gray-500">
                  Receive notifications via SMS
                </p>
              </div>
              <Switch
                checked={notificationSettings.sms_notifications}
                onCheckedChange={(checked) =>
                  setNotificationSettings((prev) => ({
                    ...prev,
                    sms_notifications: checked,
                  }))
                }
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Marketing Emails</p>
                <p className="text-sm text-gray-500">
                  Receive product updates and tips
                </p>
              </div>
              <Switch
                checked={notificationSettings.marketing_emails}
                onCheckedChange={(checked) =>
                  setNotificationSettings((prev) => ({
                    ...prev,
                    marketing_emails: checked,
                  }))
                }
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Notification Types</CardTitle>
          <CardDescription>
            Configure specific types of notifications
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Security Alerts</p>
              <p className="text-sm text-gray-500">
                Login attempts and security events
              </p>
            </div>
            <Switch
              checked={notificationSettings.security_alerts}
              onCheckedChange={(checked) =>
                setNotificationSettings((prev) => ({
                  ...prev,
                  security_alerts: checked,
                }))
              }
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Payment Notifications</p>
              <p className="text-sm text-gray-500">
                Transaction confirmations and alerts
              </p>
            </div>
            <Switch
              checked={notificationSettings.payment_notifications}
              onCheckedChange={(checked) =>
                setNotificationSettings((prev) => ({
                  ...prev,
                  payment_notifications: checked,
                }))
              }
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">AI Insights</p>
              <p className="text-sm text-gray-500">
                AI-generated financial insights and recommendations
              </p>
            </div>
            <Switch
              checked={notificationSettings.ai_insights}
              onCheckedChange={(checked) =>
                setNotificationSettings((prev) => ({
                  ...prev,
                  ai_insights: checked,
                }))
              }
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );

  const PreferencesTab = () => (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Palette className="w-5 h-5" />
            <span>Appearance</span>
          </CardTitle>
          <CardDescription>
            Customize the look and feel of your dashboard
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <Label>Theme</Label>
            <div className="grid grid-cols-3 gap-4 mt-2">
              <div
                className={`p-4 border rounded-lg cursor-pointer ${theme === "light" ? "border-blue-500 bg-blue-50" : "border-gray-200"}`}
                onClick={() => setTheme("light")}
              >
                <div className="w-full h-8 bg-white border rounded mb-2"></div>
                <p className="text-sm font-medium">Light</p>
              </div>
              <div
                className={`p-4 border rounded-lg cursor-pointer ${theme === "dark" ? "border-blue-500 bg-blue-50" : "border-gray-200"}`}
                onClick={() => setTheme("dark")}
              >
                <div className="w-full h-8 bg-gray-800 border rounded mb-2"></div>
                <p className="text-sm font-medium">Dark</p>
              </div>
              <div
                className={`p-4 border rounded-lg cursor-pointer ${theme === "auto" ? "border-blue-500 bg-blue-50" : "border-gray-200"}`}
                onClick={() => setTheme("auto")}
              >
                <div className="w-full h-8 bg-gradient-to-r from-white to-gray-800 border rounded mb-2"></div>
                <p className="text-sm font-medium">Auto</p>
              </div>
            </div>
          </div>

          <div>
            <Label htmlFor="language">Language</Label>
            <Select defaultValue="en">
              <SelectTrigger className="mt-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">English</SelectItem>
                <SelectItem value="es">Spanish</SelectItem>
                <SelectItem value="fr">French</SelectItem>
                <SelectItem value="de">German</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="timezone">Timezone</Label>
            <Select defaultValue="utc">
              <SelectTrigger className="mt-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="utc">UTC</SelectItem>
                <SelectItem value="est">Eastern Time</SelectItem>
                <SelectItem value="pst">Pacific Time</SelectItem>
                <SelectItem value="cet">Central European Time</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="currency">Default Currency</Label>
            <Select defaultValue="usd">
              <SelectTrigger className="mt-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="usd">USD - US Dollar</SelectItem>
                <SelectItem value="eur">EUR - Euro</SelectItem>
                <SelectItem value="gbp">GBP - British Pound</SelectItem>
                <SelectItem value="cad">CAD - Canadian Dollar</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Globe className="w-5 h-5" />
            <span>Regional Settings</span>
          </CardTitle>
          <CardDescription>
            Configure regional preferences for your business
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <Label htmlFor="date_format">Date Format</Label>
            <Select defaultValue="mm/dd/yyyy">
              <SelectTrigger className="mt-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="mm/dd/yyyy">MM/DD/YYYY</SelectItem>
                <SelectItem value="dd/mm/yyyy">DD/MM/YYYY</SelectItem>
                <SelectItem value="yyyy-mm-dd">YYYY-MM-DD</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="number_format">Number Format</Label>
            <Select defaultValue="1,234.56">
              <SelectTrigger className="mt-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1,234.56">1,234.56</SelectItem>
                <SelectItem value="1.234,56">1.234,56</SelectItem>
                <SelectItem value="1 234.56">1 234.56</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="fiscal_year">Fiscal Year Start</Label>
            <Select defaultValue="january">
              <SelectTrigger className="mt-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="january">January</SelectItem>
                <SelectItem value="april">April</SelectItem>
                <SelectItem value="july">July</SelectItem>
                <SelectItem value="october">October</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>
    </div>
  );

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-600 mt-1">
          Manage your account settings and preferences
        </p>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="space-y-6"
      >
        <TabsList>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="preferences">Preferences</TabsTrigger>
        </TabsList>

        <TabsContent value="profile">
          <ProfileTab />
        </TabsContent>

        <TabsContent value="security">
          <SecurityTab />
        </TabsContent>

        <TabsContent value="notifications">
          <NotificationsTab />
        </TabsContent>

        <TabsContent value="preferences">
          <PreferencesTab />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default SettingsModule;
