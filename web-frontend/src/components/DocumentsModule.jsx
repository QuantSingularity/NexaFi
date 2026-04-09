import {
  Download,
  Eye,
  File,
  FileText,
  Filter,
  Plus,
  Search,
  Share2,
  Trash2,
  Upload,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
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
import { useApp } from "../contexts/AppContext";
import apiClient from "../lib/api";

const DocumentsModule = () => {
  const { addNotification } = useApp();
  const [activeTab, setActiveTab] = useState("documents");
  const [documents, setDocuments] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [shareDialogOpen, setShareDialogOpen] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState(null);

  const loadDocuments = useCallback(async () => {
    try {
      setLoading(true);
      const [docsResponse, templatesResponse] = await Promise.allSettled([
        apiClient.getDocuments(),
        apiClient.getDocumentTemplates(),
      ]);

      if (docsResponse.status === "fulfilled") {
        setDocuments(docsResponse.value.documents || docsResponse.value || []);
      } else {
        setDocuments(MOCK_DOCUMENTS);
      }

      if (templatesResponse.status === "fulfilled") {
        setTemplates(
          templatesResponse.value.templates || templatesResponse.value || [],
        );
      } else {
        setTemplates(MOCK_TEMPLATES);
      }
    } catch (error) {
      console.error("Failed to load documents:", error);
      setDocuments(MOCK_DOCUMENTS);
      setTemplates(MOCK_TEMPLATES);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const handleDeleteDocument = async (documentId) => {
    try {
      await apiClient.deleteDocument(documentId);
      setDocuments((prev) => prev.filter((d) => d.id !== documentId));
      addNotification({
        type: "success",
        title: "Deleted",
        message: "Document deleted successfully",
      });
    } catch (error) {
      console.error("Failed to delete document:", error);
      addNotification({
        type: "error",
        title: "Error",
        message: "Failed to delete document",
      });
    }
  };

  const filteredDocuments = documents.filter((doc) => {
    const matchesSearch =
      !searchQuery ||
      doc.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.file_name?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType =
      filterType === "all" ||
      doc.document_type === filterType ||
      doc.type === filterType;
    return matchesSearch && matchesType;
  });

  const getFileIcon = (doc) => {
    const name = (doc.file_name || doc.name || "").toLowerCase();
    if (name.endsWith(".pdf"))
      return <FileText className="w-5 h-5 text-red-500" />;
    if (name.match(/\.(xlsx?|csv)$/))
      return <FileText className="w-5 h-5 text-green-500" />;
    if (name.match(/\.(docx?)$/))
      return <FileText className="w-5 h-5 text-blue-500" />;
    return <File className="w-5 h-5 text-gray-500" />;
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return "—";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-24 bg-gray-200 rounded"></div>
            ))}
          </div>
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Documents</h1>
        <p className="text-gray-600 mt-1">
          Manage, upload, and share your financial documents and templates
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        <Card>
          <CardContent className="p-6 flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Documents</p>
              <p className="text-2xl font-bold">{documents.length}</p>
            </div>
            <div className="p-3 bg-blue-100 rounded-full">
              <FileText className="w-6 h-6 text-blue-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6 flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Templates</p>
              <p className="text-2xl font-bold">{templates.length}</p>
            </div>
            <div className="p-3 bg-purple-100 rounded-full">
              <File className="w-6 h-6 text-purple-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6 flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Shared</p>
              <p className="text-2xl font-bold">
                {documents.filter((d) => d.is_shared || d.shared).length}
              </p>
            </div>
            <div className="p-3 bg-green-100 rounded-full">
              <Share2 className="w-6 h-6 text-green-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="space-y-6"
      >
        <TabsList>
          <TabsTrigger value="documents">My Documents</TabsTrigger>
          <TabsTrigger value="templates">Templates</TabsTrigger>
        </TabsList>

        <TabsContent value="documents">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Documents</CardTitle>
                  <CardDescription>
                    All your uploaded financial documents
                  </CardDescription>
                </div>
                <Dialog
                  open={uploadDialogOpen}
                  onOpenChange={setUploadDialogOpen}
                >
                  <DialogTrigger asChild>
                    <Button>
                      <Upload className="w-4 h-4 mr-2" />
                      Upload Document
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Upload Document</DialogTitle>
                      <DialogDescription>
                        Upload a new document to your account
                      </DialogDescription>
                    </DialogHeader>
                    <UploadDocumentForm
                      onSuccess={() => {
                        setUploadDialogOpen(false);
                        loadDocuments();
                      }}
                      onError={(msg) =>
                        addNotification({
                          type: "error",
                          title: "Error",
                          message: msg,
                        })
                      }
                    />
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              {/* Filters */}
              <div className="flex items-center space-x-3 mb-4">
                <div className="relative flex-1 max-w-sm">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    placeholder="Search documents..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9"
                  />
                </div>
                <Select value={filterType} onValueChange={setFilterType}>
                  <SelectTrigger className="w-44">
                    <Filter className="w-4 h-4 mr-2" />
                    <SelectValue placeholder="Filter by type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="invoice">Invoice</SelectItem>
                    <SelectItem value="contract">Contract</SelectItem>
                    <SelectItem value="report">Report</SelectItem>
                    <SelectItem value="receipt">Receipt</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {filteredDocuments.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <FileText className="w-12 h-12 text-gray-300 mb-4" />
                  <p className="text-gray-500 font-medium">
                    No documents found
                  </p>
                  <p className="text-sm text-gray-400 mt-1">
                    {searchQuery || filterType !== "all"
                      ? "Try adjusting your search or filter"
                      : "Upload your first document to get started"}
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Size</TableHead>
                      <TableHead>Uploaded</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredDocuments.map((doc) => (
                      <TableRow key={doc.id}>
                        <TableCell>
                          <div className="flex items-center space-x-3">
                            {getFileIcon(doc)}
                            <span className="font-medium truncate max-w-xs">
                              {doc.name || doc.file_name}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="capitalize">
                            {doc.document_type || doc.type || "other"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-gray-500">
                          {formatFileSize(doc.file_size || doc.size)}
                        </TableCell>
                        <TableCell className="text-gray-500">
                          {doc.created_at
                            ? new Date(doc.created_at).toLocaleDateString()
                            : "—"}
                        </TableCell>
                        <TableCell>
                          {doc.is_shared || doc.shared ? (
                            <Badge className="bg-green-100 text-green-800">
                              Shared
                            </Badge>
                          ) : (
                            <Badge variant="secondary">Private</Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center space-x-1">
                            <Button variant="ghost" size="sm" title="Preview">
                              <Eye className="w-4 h-4" />
                            </Button>
                            <Button variant="ghost" size="sm" title="Download">
                              <Download className="w-4 h-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              title="Share"
                              onClick={() => {
                                setSelectedDocument(doc);
                                setShareDialogOpen(true);
                              }}
                            >
                              <Share2 className="w-4 h-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              title="Delete"
                              className="text-red-500 hover:text-red-700"
                              onClick={() => handleDeleteDocument(doc.id)}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="templates">
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">Document Templates</h2>
              <Button variant="outline">
                <Plus className="w-4 h-4 mr-2" />
                Create Template
              </Button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {templates.map((template) => (
                <Card
                  key={template.id}
                  className="hover:shadow-md transition-shadow"
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div className="p-2 bg-blue-100 rounded-lg">
                        <FileText className="w-5 h-5 text-blue-600" />
                      </div>
                      <Badge variant="outline" className="capitalize">
                        {template.category || template.type || "general"}
                      </Badge>
                    </div>
                    <CardTitle className="text-base mt-3">
                      {template.name || template.template_name}
                    </CardTitle>
                    <CardDescription className="text-sm">
                      {template.description || "Financial document template"}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Button variant="outline" className="w-full" size="sm">
                      <Download className="w-4 h-4 mr-2" />
                      Use Template
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* Share Dialog */}
      <Dialog open={shareDialogOpen} onOpenChange={setShareDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Share Document</DialogTitle>
            <DialogDescription>
              Share "{selectedDocument?.name || selectedDocument?.file_name}"
              with others
            </DialogDescription>
          </DialogHeader>
          <ShareDocumentForm
            document={selectedDocument}
            onSuccess={() => {
              setShareDialogOpen(false);
              loadDocuments();
              addNotification({
                type: "success",
                title: "Shared",
                message: "Document shared successfully",
              });
            }}
            onError={(msg) =>
              addNotification({ type: "error", title: "Error", message: msg })
            }
          />
        </DialogContent>
      </Dialog>
    </div>
  );
};

const UploadDocumentForm = ({ onSuccess, onError }) => {
  const fileInputRef = useRef(null);
  const [formData, setFormData] = useState({
    document_type: "other",
    description: "",
  });
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const handleFileSelect = (file) => {
    if (!file) return;
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      onError("File size must be less than 10MB");
      return;
    }
    setSelectedFile(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      onError("Please select a file to upload");
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", selectedFile);
      fd.append("document_type", formData.document_type);
      fd.append("description", formData.description);
      await apiClient.uploadDocument(fd);
      onSuccess();
    } catch (error) {
      onError(error.message || "Failed to upload document");
    } finally {
      setUploading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Drop zone */}
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          dragOver
            ? "border-blue-400 bg-blue-50"
            : "border-gray-300 hover:border-gray-400"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
        {selectedFile ? (
          <div>
            <p className="font-medium text-gray-700">{selectedFile.name}</p>
            <p className="text-sm text-gray-500">
              {(selectedFile.size / 1024).toFixed(1)} KB
            </p>
          </div>
        ) : (
          <div>
            <p className="text-gray-600">
              Drop your file here or click to browse
            </p>
            <p className="text-sm text-gray-400 mt-1">
              PDF, DOCX, XLSX up to 10MB
            </p>
          </div>
        )}
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.txt"
          onChange={(e) => handleFileSelect(e.target.files?.[0])}
        />
      </div>

      <div>
        <Label htmlFor="doc_type">Document Type</Label>
        <Select
          value={formData.document_type}
          onValueChange={(val) =>
            setFormData((p) => ({ ...p, document_type: val }))
          }
        >
          <SelectTrigger className="mt-1">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="invoice">Invoice</SelectItem>
            <SelectItem value="contract">Contract</SelectItem>
            <SelectItem value="report">Report</SelectItem>
            <SelectItem value="receipt">Receipt</SelectItem>
            <SelectItem value="other">Other</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div>
        <Label htmlFor="doc_description">Description (optional)</Label>
        <Input
          id="doc_description"
          value={formData.description}
          onChange={(e) =>
            setFormData((p) => ({ ...p, description: e.target.value }))
          }
          placeholder="Brief description of the document"
          className="mt-1"
        />
      </div>

      <Button
        type="submit"
        className="w-full"
        disabled={uploading || !selectedFile}
      >
        {uploading ? "Uploading..." : "Upload Document"}
      </Button>
    </form>
  );
};

const ShareDocumentForm = ({ document, onSuccess, onError }) => {
  const [shareData, setShareData] = useState({
    email: "",
    permission: "view",
    message: "",
  });
  const [sharing, setSharing] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!document?.id) return;
    setSharing(true);
    try {
      await apiClient.shareDocument(document.id, shareData);
      onSuccess();
    } catch (error) {
      onError(error.message || "Failed to share document");
    } finally {
      setSharing(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor="share_email">Email Address</Label>
        <Input
          id="share_email"
          type="email"
          value={shareData.email}
          onChange={(e) =>
            setShareData((p) => ({ ...p, email: e.target.value }))
          }
          placeholder="colleague@company.com"
          required
          className="mt-1"
        />
      </div>
      <div>
        <Label htmlFor="share_permission">Permission</Label>
        <Select
          value={shareData.permission}
          onValueChange={(val) =>
            setShareData((p) => ({ ...p, permission: val }))
          }
        >
          <SelectTrigger className="mt-1">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="view">View only</SelectItem>
            <SelectItem value="download">View & Download</SelectItem>
            <SelectItem value="edit">Edit</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div>
        <Label htmlFor="share_message">Message (optional)</Label>
        <Input
          id="share_message"
          value={shareData.message}
          onChange={(e) =>
            setShareData((p) => ({ ...p, message: e.target.value }))
          }
          placeholder="Add a personal message..."
          className="mt-1"
        />
      </div>
      <Button type="submit" className="w-full" disabled={sharing}>
        {sharing ? "Sharing..." : "Share Document"}
      </Button>
    </form>
  );
};

// Mock data for when API is unavailable
const MOCK_DOCUMENTS = [
  {
    id: 1,
    name: "Q2 2024 Financial Report.pdf",
    file_name: "Q2 2024 Financial Report.pdf",
    document_type: "report",
    file_size: 245760,
    created_at: "2024-06-10T10:00:00Z",
    is_shared: false,
  },
  {
    id: 2,
    name: "Client Contract - ABC Corp.docx",
    file_name: "Client Contract - ABC Corp.docx",
    document_type: "contract",
    file_size: 89120,
    created_at: "2024-06-08T14:30:00Z",
    is_shared: true,
  },
  {
    id: 3,
    name: "Invoice #1042.pdf",
    file_name: "Invoice #1042.pdf",
    document_type: "invoice",
    file_size: 54320,
    created_at: "2024-06-05T09:15:00Z",
    is_shared: false,
  },
];

const MOCK_TEMPLATES = [
  {
    id: 1,
    name: "Standard Invoice Template",
    template_name: "Standard Invoice Template",
    category: "invoice",
    description: "Professional invoice template with tax calculations",
  },
  {
    id: 2,
    name: "Service Agreement",
    template_name: "Service Agreement",
    category: "contract",
    description: "Basic service agreement template for freelancers",
  },
  {
    id: 3,
    name: "Expense Report",
    template_name: "Expense Report",
    category: "report",
    description: "Monthly expense tracking and reporting template",
  },
  {
    id: 4,
    name: "Balance Sheet Template",
    template_name: "Balance Sheet Template",
    category: "report",
    description: "Standard balance sheet for small businesses",
  },
];

export default DocumentsModule;
