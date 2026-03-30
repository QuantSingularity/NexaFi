import { motion } from "framer-motion";
import {
  BarChart3,
  Building,
  ChevronRight,
  DollarSign,
  Download,
  Eye,
  FileText,
  Filter,
  MoreVertical,
  PieChart,
  Plus,
  Search,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  PieChart as RechartsPieChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApp } from "../contexts/MobileContext";
import "../App.css";

const MobileAccountingModule = () => {
  const { addNotification, isOnline } = useApp();
  const [activeTab, setActiveTab] = useState("overview");
  const [_loading, _setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPeriod, setSelectedPeriod] = useState("current-month");

  // Mock data for mobile accounting
  const [accountsData] = useState([
    { id: 1, name: "Cash", type: "Asset", balance: 25430.5, change: 12.5 },
    {
      id: 2,
      name: "Accounts Receivable",
      type: "Asset",
      balance: 45200.0,
      change: -5.2,
    },
    {
      id: 3,
      name: "Office Equipment",
      type: "Asset",
      balance: 15000.0,
      change: 0,
    },
    {
      id: 4,
      name: "Accounts Payable",
      type: "Liability",
      balance: -8500.0,
      change: 15.3,
    },
    {
      id: 5,
      name: "Business Loan",
      type: "Liability",
      balance: -25000.0,
      change: -2.1,
    },
    {
      id: 6,
      name: "Owner Equity",
      type: "Equity",
      balance: 52130.5,
      change: 8.7,
    },
  ]);

  const [journalEntries] = useState([
    {
      id: 1,
      date: "2024-06-10",
      description: "Client payment received",
      reference: "INV-001",
      amount: 5000.0,
      accounts: [
        { name: "Cash", debit: 5000.0, credit: 0 },
        { name: "Accounts Receivable", debit: 0, credit: 5000.0 },
      ],
    },
    {
      id: 2,
      date: "2024-06-09",
      description: "Office rent payment",
      reference: "RENT-06",
      amount: 2500.0,
      accounts: [
        { name: "Rent Expense", debit: 2500.0, credit: 0 },
        { name: "Cash", debit: 0, credit: 2500.0 },
      ],
    },
    {
      id: 3,
      date: "2024-06-08",
      description: "Equipment purchase",
      reference: "EQ-001",
      amount: 3500.0,
      accounts: [
        { name: "Office Equipment", debit: 3500.0, credit: 0 },
        { name: "Cash", debit: 0, credit: 3500.0 },
      ],
    },
  ]);

  const [financialData] = useState({
    assets: 85630.5,
    liabilities: 33500.0,
    equity: 52130.5,
    revenue: 125000.0,
    expenses: 72869.5,
    netIncome: 52130.5,
  });

  const [chartData] = useState([
    { name: "Assets", value: 85630.5, color: "#3b82f6" },
    { name: "Liabilities", value: 33500.0, color: "#ef4444" },
    { name: "Equity", value: 52130.5, color: "#10b981" },
  ]);

  const [monthlyData] = useState([
    { month: "Jan", revenue: 18000, expenses: 12000 },
    { month: "Feb", revenue: 22000, expenses: 14000 },
    { month: "Mar", revenue: 25000, expenses: 15000 },
    { month: "Apr", revenue: 28000, expenses: 16000 },
    { month: "May", revenue: 24000, expenses: 13000 },
    { month: "Jun", revenue: 26000, expenses: 14000 },
  ]);

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(Math.abs(amount));
  };

  const getAccountTypeColor = (type) => {
    switch (type) {
      case "Asset":
        return "bg-blue-100 text-blue-800";
      case "Liability":
        return "bg-red-100 text-red-800";
      case "Equity":
        return "bg-green-100 text-green-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const OverviewTab = () => (
    <div className="space-y-6">
      {/* Financial Summary Cards */}
      <div className="grid grid-cols-2 gap-4">
        <Card className="bg-gradient-to-r from-blue-500 to-blue-600 text-white">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-blue-100 text-xs">Total Assets</p>
                <p className="text-xl font-bold">
                  {formatCurrency(financialData.assets)}
                </p>
              </div>
              <TrendingUp className="w-8 h-8 text-blue-200" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-r from-green-500 to-green-600 text-white">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-green-100 text-xs">Net Income</p>
                <p className="text-xl font-bold">
                  {formatCurrency(financialData.netIncome)}
                </p>
              </div>
              <DollarSign className="w-8 h-8 text-green-200" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-xs">Liabilities</p>
                <p className="text-lg font-bold text-red-600">
                  {formatCurrency(financialData.liabilities)}
                </p>
              </div>
              <TrendingDown className="w-6 h-6 text-red-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-xs">Equity</p>
                <p className="text-lg font-bold text-green-600">
                  {formatCurrency(financialData.equity)}
                </p>
              </div>
              <Building className="w-6 h-6 text-green-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Balance Sheet Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Balance Sheet</CardTitle>
          <CardDescription>Current financial position</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={200}>
            <RechartsPieChart>
              <RechartsPieChart
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={80}
                paddingAngle={5}
                dataKey="value"
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </RechartsPieChart>
            </RechartsPieChart>
          </ResponsiveContainer>
          <div className="flex justify-center space-x-4 mt-4">
            {chartData.map((item, index) => (
              <div key={index} className="flex items-center space-x-2">
                <div
                  className={`w-3 h-3 rounded-full`}
                  style={{ backgroundColor: item.color }}
                ></div>
                <span className="text-xs text-gray-600">{item.name}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Monthly Performance */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Monthly Performance</CardTitle>
          <CardDescription>Revenue vs Expenses</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={monthlyData}>
              <XAxis dataKey="month" axisLine={false} tickLine={false} />
              <YAxis hide />
              <Bar dataKey="revenue" fill="#3b82f6" radius={[2, 2, 0, 0]} />
              <Bar dataKey="expenses" fill="#ef4444" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 gap-3">
        <Button className="h-12 bg-blue-600 hover:bg-blue-700">
          <Plus className="w-4 h-4 mr-2" />
          New Entry
        </Button>
        <Button variant="outline" className="h-12">
          <FileText className="w-4 h-4 mr-2" />
          Reports
        </Button>
      </div>
    </div>
  );

  const AccountsTab = () => (
    <div className="space-y-4">
      {/* Search and Filter */}
      <div className="flex space-x-2">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <Input
            placeholder="Search accounts..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        <Button variant="outline" size="sm">
          <Filter className="w-4 h-4" />
        </Button>
      </div>

      {/* Accounts List */}
      <div className="space-y-3">
        {accountsData
          .filter(
            (account) =>
              account.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
              account.type.toLowerCase().includes(searchQuery.toLowerCase()),
          )
          .map((account) => (
            <motion.div
              key={account.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              whileTap={{ scale: 0.98 }}
            >
              <Card className="cursor-pointer hover:shadow-md transition-shadow">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-1">
                        <h3 className="font-medium text-gray-900">
                          {account.name}
                        </h3>
                        <Badge className={getAccountTypeColor(account.type)}>
                          {account.type}
                        </Badge>
                      </div>
                      <p className="text-lg font-bold text-gray-900">
                        {account.balance < 0 ? "-" : ""}
                        {formatCurrency(account.balance)}
                      </p>
                      {account.change !== 0 && (
                        <div className="flex items-center space-x-1 mt-1">
                          {account.change > 0 ? (
                            <TrendingUp className="w-3 h-3 text-green-500" />
                          ) : (
                            <TrendingDown className="w-3 h-3 text-red-500" />
                          )}
                          <span
                            className={`text-xs ${account.change > 0 ? "text-green-600" : "text-red-600"}`}
                          >
                            {Math.abs(account.change)}%
                          </span>
                        </div>
                      )}
                    </div>
                    <ChevronRight className="w-5 h-5 text-gray-400" />
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
      </div>

      {/* Add Account Button */}
      <Button className="w-full h-12 bg-blue-600 hover:bg-blue-700">
        <Plus className="w-4 h-4 mr-2" />
        Add New Account
      </Button>
    </div>
  );

  const JournalTab = () => (
    <div className="space-y-4">
      {/* Period Selector */}
      <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="current-month">Current Month</SelectItem>
          <SelectItem value="last-month">Last Month</SelectItem>
          <SelectItem value="current-quarter">Current Quarter</SelectItem>
          <SelectItem value="current-year">Current Year</SelectItem>
        </SelectContent>
      </Select>

      {/* Journal Entries */}
      <div className="space-y-3">
        {journalEntries.map((entry) => (
          <motion.div
            key={entry.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            whileTap={{ scale: 0.98 }}
          >
            <Card className="cursor-pointer hover:shadow-md transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-medium text-gray-900">
                      {entry.description}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {entry.date} • {entry.reference}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-bold text-gray-900">
                      {formatCurrency(entry.amount)}
                    </p>
                    <Button variant="ghost" size="sm" className="p-1">
                      <MoreVertical className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  {entry.accounts.map((account, index) => (
                    <div key={index} className="flex justify-between text-sm">
                      <span className="text-gray-600">{account.name}</span>
                      <div className="flex space-x-4">
                        {account.debit > 0 && (
                          <span className="text-green-600">
                            Dr: {formatCurrency(account.debit)}
                          </span>
                        )}
                        {account.credit > 0 && (
                          <span className="text-red-600">
                            Cr: {formatCurrency(account.credit)}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Add Entry Button */}
      <Button className="w-full h-12 bg-blue-600 hover:bg-blue-700">
        <Plus className="w-4 h-4 mr-2" />
        New Journal Entry
      </Button>
    </div>
  );

  const ReportsTab = () => (
    <div className="space-y-4">
      {/* Report Cards */}
      <div className="grid grid-cols-1 gap-4">
        {[
          {
            title: "Balance Sheet",
            description: "Assets, liabilities, and equity",
            icon: BarChart3,
          },
          {
            title: "Income Statement",
            description: "Revenue and expenses",
            icon: TrendingUp,
          },
          {
            title: "Cash Flow Statement",
            description: "Cash inflows and outflows",
            icon: DollarSign,
          },
          {
            title: "Trial Balance",
            description: "Account balances verification",
            icon: PieChart,
          },
        ].map((report, index) => {
          const Icon = report.icon;
          return (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              whileTap={{ scale: 0.98 }}
            >
              <Card className="cursor-pointer hover:shadow-md transition-shadow">
                <CardContent className="p-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                      <Icon className="w-6 h-6 text-blue-600" />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-medium text-gray-900">
                        {report.title}
                      </h3>
                      <p className="text-sm text-gray-500">
                        {report.description}
                      </p>
                    </div>
                    <div className="flex space-x-2">
                      <Button variant="ghost" size="sm">
                        <Eye className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm">
                        <Download className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* Custom Report Builder */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Custom Report</CardTitle>
          <CardDescription>Build your own financial report</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Select>
            <SelectTrigger>
              <SelectValue placeholder="Select report type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="profit-loss">Profit & Loss</SelectItem>
              <SelectItem value="balance-sheet">Balance Sheet</SelectItem>
              <SelectItem value="cash-flow">Cash Flow</SelectItem>
              <SelectItem value="custom">Custom</SelectItem>
            </SelectContent>
          </Select>

          <div className="grid grid-cols-2 gap-3">
            <Select>
              <SelectTrigger>
                <SelectValue placeholder="From date" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="this-month">This Month</SelectItem>
                <SelectItem value="last-month">Last Month</SelectItem>
                <SelectItem value="this-quarter">This Quarter</SelectItem>
                <SelectItem value="this-year">This Year</SelectItem>
              </SelectContent>
            </Select>

            <Select>
              <SelectTrigger>
                <SelectValue placeholder="To date" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="today">Today</SelectItem>
                <SelectItem value="end-month">End of Month</SelectItem>
                <SelectItem value="end-quarter">End of Quarter</SelectItem>
                <SelectItem value="end-year">End of Year</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Button className="w-full">Generate Report</Button>
        </CardContent>
      </Card>
    </div>
  );

  return (
    <div className="p-4 pb-20">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Accounting</h1>
        <p className="text-gray-600">
          Manage your financial records and reports
        </p>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="space-y-6"
      >
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview" className="text-xs">
            Overview
          </TabsTrigger>
          <TabsTrigger value="accounts" className="text-xs">
            Accounts
          </TabsTrigger>
          <TabsTrigger value="journal" className="text-xs">
            Journal
          </TabsTrigger>
          <TabsTrigger value="reports" className="text-xs">
            Reports
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <OverviewTab />
        </TabsContent>

        <TabsContent value="accounts">
          <AccountsTab />
        </TabsContent>

        <TabsContent value="journal">
          <JournalTab />
        </TabsContent>

        <TabsContent value="reports">
          <ReportsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default MobileAccountingModule;
