import {
  AlertCircle,
  BarChart3,
  Calculator,
  CheckCircle,
  Clock,
  Download,
  Edit,
  Eye,
  FileText,
  Filter,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useApp } from "../contexts/AppContext";
import apiClient from "../lib/api";

const AccountingModule = () => {
  const { addNotification } = useApp();

  const [activeTab, setActiveTab] = useState("overview");
  const [accounts, setAccounts] = useState([]);
  const [journalEntries, setJournalEntries] = useState([]);
  const [reports, setReports] = useState({});
  const [loading, setLoading] = useState(true);

  const loadAccountingData = useCallback(async () => {
    try {
      setLoading(true);

      // Load accounts
      const accountsResponse = await apiClient.getAccounts();
      setAccounts(accountsResponse.accounts || []);

      // Load journal entries
      const entriesResponse = await apiClient.getJournalEntries({
        per_page: 10,
      });
      setJournalEntries(entriesResponse.journal_entries || []);

      // Load trial balance
      const trialBalanceResponse = await apiClient.getTrialBalance();
      setReports((prev) => ({ ...prev, trialBalance: trialBalanceResponse }));
    } catch (error) {
      console.error("Failed to load accounting data:", error);
      addNotification({
        type: "error",
        title: "Error",
        message: "Failed to load accounting data",
      });
    } finally {
      setLoading(false);
    }
  }, [addNotification]);

  useEffect(() => {
    loadAccountingData();
  }, [loadAccountingData]);

  const AccountsOverview = () => {
    const accountsByType = accounts.reduce((acc, account) => {
      if (!acc[account.account_type]) {
        acc[account.account_type] = [];
      }
      acc[account.account_type].push(account);
      return acc;
    }, {});

    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold">Chart of Accounts</h2>
          <div className="flex space-x-2">
            <Button variant="outline">
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
            <Dialog>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="w-4 h-4 mr-2" />
                  Add Account
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create New Account</DialogTitle>
                  <DialogDescription>
                    Add a new account to your chart of accounts
                  </DialogDescription>
                </DialogHeader>
                <CreateAccountForm onSuccess={loadAccountingData} />
              </DialogContent>
            </Dialog>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.entries(accountsByType).map(([type, typeAccounts]) => (
            <Card key={type}>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg capitalize">
                  {type.replace("_", " ")}
                </CardTitle>
                <CardDescription>
                  {typeAccounts.length} accounts
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {typeAccounts.slice(0, 3).map((account) => (
                    <div
                      key={account.id}
                      className="flex justify-between text-sm"
                    >
                      <span className="truncate">{account.account_name}</span>
                      <span className="font-mono">{account.account_code}</span>
                    </div>
                  ))}
                  {typeAccounts.length > 3 && (
                    <div className="text-xs text-gray-500">
                      +{typeAccounts.length - 3} more
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <Card>
          <CardHeader>
            <CardTitle>All Accounts</CardTitle>
            <CardDescription>
              Complete list of your chart of accounts
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center space-x-2">
                <Search className="w-4 h-4 text-gray-400" />
                <Input placeholder="Search accounts..." className="max-w-sm" />
                <Select>
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="Filter by type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="asset">Assets</SelectItem>
                    <SelectItem value="liability">Liabilities</SelectItem>
                    <SelectItem value="equity">Equity</SelectItem>
                    <SelectItem value="revenue">Revenue</SelectItem>
                    <SelectItem value="expense">Expenses</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Code</TableHead>
                    <TableHead>Account Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Balance</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {accounts.map((account) => (
                    <TableRow key={account.id}>
                      <TableCell className="font-mono">
                        {account.account_code}
                      </TableCell>
                      <TableCell className="font-medium">
                        {account.account_name}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="capitalize">
                          {account.account_type.replace("_", " ")}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono">$0.00</TableCell>
                      <TableCell>
                        <Badge
                          variant={account.is_active ? "default" : "secondary"}
                        >
                          {account.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex space-x-2">
                          <Button variant="ghost" size="sm">
                            <Eye className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm">
                            <Edit className="w-4 h-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  };

  const JournalEntries = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Journal Entries</h2>
        <div className="flex space-x-2">
          <Button variant="outline">
            <Filter className="w-4 h-4 mr-2" />
            Filter
          </Button>
          <Dialog>
            <DialogTrigger asChild>
              <Button>
                <Plus className="w-4 h-4 mr-2" />
                New Entry
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl">
              <DialogHeader>
                <DialogTitle>Create Journal Entry</DialogTitle>
                <DialogDescription>
                  Record a new journal entry with debits and credits
                </DialogDescription>
              </DialogHeader>
              <CreateJournalEntryForm
                onSuccess={loadAccountingData}
                accounts={accounts}
              />
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Card>
        <CardContent className="p-6">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Entry #</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {journalEntries.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell className="font-mono">
                    {entry.entry_number}
                  </TableCell>
                  <TableCell>{entry.entry_date}</TableCell>
                  <TableCell>{entry.description}</TableCell>
                  <TableCell className="font-mono">
                    ${entry.total_amount}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        entry.status === "posted" ? "default" : "secondary"
                      }
                    >
                      {entry.status === "posted" ? (
                        <>
                          <CheckCircle className="w-3 h-3 mr-1" />
                          Posted
                        </>
                      ) : (
                        <>
                          <Clock className="w-3 h-3 mr-1" />
                          Draft
                        </>
                      )}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex space-x-2">
                      <Button variant="ghost" size="sm">
                        <Eye className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm">
                        <Edit className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );

  const FinancialReports = () => (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Financial Reports</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="cursor-pointer hover:shadow-lg transition-shadow">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <BarChart3 className="w-5 h-5" />
              <span>Trial Balance</span>
            </CardTitle>
            <CardDescription>Verify that debits equal credits</CardDescription>
          </CardHeader>
          <CardContent>
            <Button className="w-full">Generate Report</Button>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:shadow-lg transition-shadow">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <FileText className="w-5 h-5" />
              <span>Balance Sheet</span>
            </CardTitle>
            <CardDescription>Assets, liabilities, and equity</CardDescription>
          </CardHeader>
          <CardContent>
            <Button className="w-full">Generate Report</Button>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:shadow-lg transition-shadow">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Calculator className="w-5 h-5" />
              <span>Income Statement</span>
            </CardTitle>
            <CardDescription>Revenue and expenses over time</CardDescription>
          </CardHeader>
          <CardContent>
            <Button className="w-full">Generate Report</Button>
          </CardContent>
        </Card>
      </div>

      {reports.trialBalance && (
        <Card>
          <CardHeader>
            <CardTitle>Trial Balance</CardTitle>
            <CardDescription>
              As of {reports.trialBalance.as_of_date}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center p-4 bg-gray-50 rounded-lg">
                <span className="font-medium">Total Debits:</span>
                <span className="font-mono font-bold">
                  ${reports.trialBalance.total_debits}
                </span>
              </div>
              <div className="flex justify-between items-center p-4 bg-gray-50 rounded-lg">
                <span className="font-medium">Total Credits:</span>
                <span className="font-mono font-bold">
                  ${reports.trialBalance.total_credits}
                </span>
              </div>
              <div
                className={`flex justify-between items-center p-4 rounded-lg ${
                  reports.trialBalance.is_balanced ? "bg-green-50" : "bg-red-50"
                }`}
              >
                <span className="font-medium">Status:</span>
                <Badge
                  variant={
                    reports.trialBalance.is_balanced ? "default" : "destructive"
                  }
                >
                  {reports.trialBalance.is_balanced ? (
                    <>
                      <CheckCircle className="w-3 h-3 mr-1" />
                      Balanced
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-3 h-3 mr-1" />
                      Unbalanced
                    </>
                  )}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-32 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Accounting</h1>
        <p className="text-gray-600 mt-1">
          Manage your chart of accounts, journal entries, and financial reports
        </p>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="space-y-6"
      >
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="accounts">Accounts</TabsTrigger>
          <TabsTrigger value="journal">Journal Entries</TabsTrigger>
          <TabsTrigger value="reports">Reports</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <AccountsOverview />
        </TabsContent>

        <TabsContent value="accounts">
          <AccountsOverview />
        </TabsContent>

        <TabsContent value="journal">
          <JournalEntries />
        </TabsContent>

        <TabsContent value="reports">
          <FinancialReports />
        </TabsContent>
      </Tabs>
    </div>
  );
};

// Create Account Form Component
const CreateAccountForm = ({ onSuccess }) => {
  const [formData, setFormData] = useState({
    account_code: "",
    account_name: "",
    account_type: "",
    account_subtype: "",
    normal_balance: "debit",
    description: "",
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await apiClient.createAccount(formData);
      onSuccess();
    } catch (error) {
      console.error("Failed to create account:", error);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="account_code">Account Code</Label>
          <Input
            id="account_code"
            value={formData.account_code}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, account_code: e.target.value }))
            }
            placeholder="e.g., 1000"
            required
          />
        </div>
        <div>
          <Label htmlFor="account_name">Account Name</Label>
          <Input
            id="account_name"
            value={formData.account_name}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, account_name: e.target.value }))
            }
            placeholder="e.g., Cash"
            required
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="account_type">Account Type</Label>
          <Select
            value={formData.account_type}
            onValueChange={(value) =>
              setFormData((prev) => ({ ...prev, account_type: value }))
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="Select type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="asset">Asset</SelectItem>
              <SelectItem value="liability">Liability</SelectItem>
              <SelectItem value="equity">Equity</SelectItem>
              <SelectItem value="revenue">Revenue</SelectItem>
              <SelectItem value="expense">Expense</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label htmlFor="normal_balance">Normal Balance</Label>
          <Select
            value={formData.normal_balance}
            onValueChange={(value) =>
              setFormData((prev) => ({ ...prev, normal_balance: value }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="debit">Debit</SelectItem>
              <SelectItem value="credit">Credit</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div>
        <Label htmlFor="description">Description</Label>
        <Textarea
          id="description"
          value={formData.description}
          onChange={(e) =>
            setFormData((prev) => ({ ...prev, description: e.target.value }))
          }
          placeholder="Optional description"
        />
      </div>

      <Button type="submit" className="w-full">
        Create Account
      </Button>
    </form>
  );
};

// Create Journal Entry Form Component
const CreateJournalEntryForm = ({ onSuccess, accounts }) => {
  const [formData, setFormData] = useState({
    description: "",
    entry_date: new Date().toISOString().split("T")[0],
    lines: [
      { account_id: "", description: "", debit_amount: "", credit_amount: "" },
      { account_id: "", description: "", debit_amount: "", credit_amount: "" },
    ],
  });

  const addLine = () => {
    setFormData((prev) => ({
      ...prev,
      lines: [
        ...prev.lines,
        {
          account_id: "",
          description: "",
          debit_amount: "",
          credit_amount: "",
        },
      ],
    }));
  };

  const removeLine = (index) => {
    setFormData((prev) => ({
      ...prev,
      lines: prev.lines.filter((_, i) => i !== index),
    }));
  };

  const updateLine = (index, field, value) => {
    setFormData((prev) => ({
      ...prev,
      lines: prev.lines.map((line, i) =>
        i === index ? { ...line, [field]: value } : line,
      ),
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await apiClient.createJournalEntry({
        ...formData,
        auto_post: true,
      });
      onSuccess();
    } catch (error) {
      console.error("Failed to create journal entry:", error);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="description">Description</Label>
          <Input
            id="description"
            value={formData.description}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, description: e.target.value }))
            }
            placeholder="Journal entry description"
            required
          />
        </div>
        <div>
          <Label htmlFor="entry_date">Date</Label>
          <Input
            id="entry_date"
            type="date"
            value={formData.entry_date}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, entry_date: e.target.value }))
            }
            required
          />
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h4 className="font-medium">Journal Entry Lines</h4>
          <Button type="button" variant="outline" onClick={addLine}>
            <Plus className="w-4 h-4 mr-2" />
            Add Line
          </Button>
        </div>

        {formData.lines.map((line, index) => (
          <div
            key={index}
            className="grid grid-cols-12 gap-2 items-end p-4 border rounded-lg"
          >
            <div className="col-span-4">
              <Label>Account</Label>
              <Select
                value={line.account_id}
                onValueChange={(value) =>
                  updateLine(index, "account_id", value)
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select account" />
                </SelectTrigger>
                <SelectContent>
                  {accounts.map((account) => (
                    <SelectItem key={account.id} value={account.id}>
                      {account.account_code} - {account.account_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="col-span-3">
              <Label>Description</Label>
              <Input
                value={line.description}
                onChange={(e) =>
                  updateLine(index, "description", e.target.value)
                }
                placeholder="Line description"
              />
            </div>
            <div className="col-span-2">
              <Label>Debit</Label>
              <Input
                type="number"
                step="0.01"
                value={line.debit_amount}
                onChange={(e) =>
                  updateLine(index, "debit_amount", e.target.value)
                }
                placeholder="0.00"
              />
            </div>
            <div className="col-span-2">
              <Label>Credit</Label>
              <Input
                type="number"
                step="0.01"
                value={line.credit_amount}
                onChange={(e) =>
                  updateLine(index, "credit_amount", e.target.value)
                }
                placeholder="0.00"
              />
            </div>
            <div className="col-span-1">
              {formData.lines.length > 2 && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => removeLine(index)}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>

      <Button type="submit" className="w-full">
        Create Journal Entry
      </Button>
    </form>
  );
};

export default AccountingModule;
