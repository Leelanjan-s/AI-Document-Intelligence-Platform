"use client";

import React, { useState, useEffect, useRef } from "react";
import Image from "next/image";

// Types
interface Document {
  id: string;
  name: string;
  storage_path: string;
  status: "uploaded" | "processing" | "review_needed" | "completed" | "failed";
  mime_type: string;
  file_size: number;
  confidence_score: number | null;
  created_at: string;
  updated_at: string;
  doc_type_name?: string;
  extracted_data?: Record<string, any>;
  validation_errors?: string[];
  field_confidences?: Record<string, number>;
  fileUrl?: string;
}

interface MetricSummary {
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  review_needed_runs: number;
  average_latency_ms: number;
  total_cost: number;
}

export default function Home() {
  // Authentication State
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [userRole, setUserRole] = useState<string>("admin");
  const [userEmail, setUserEmail] = useState<string>("reviewer@acme.com");
  const [authToken, setAuthToken] = useState<string>("");
  const [showPassword, setShowPassword] = useState<boolean>(false);
  
  // Login Form States
  const [loginEmail, setLoginEmail] = useState<string>("");
  const [loginPassword, setLoginPassword] = useState<string>("");
  const [loginError, setLoginError] = useState<string>("");
  const [isLoggingIn, setIsLoggingIn] = useState<boolean>(false);

  // App General State
  const [activeTab, setActiveTab] = useState<string>("dashboard");
  const [apiMode, setApiMode] = useState<"api" | "demo">("demo");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [metrics, setMetrics] = useState<MetricSummary>({
    total_runs: 0,
    completed_runs: 0,
    failed_runs: 0,
    review_needed_runs: 0,
    average_latency_ms: 0,
    total_cost: 0.0
  });

  // Upload Management
  const [uploadProgress, setUploadProgress] = useState<{ filename: string; percent: number } | null>(null);
  const [dragActive, setDragActive] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Review & Detail View Management
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [editingData, setEditingData] = useState<Record<string, any>>({});
  const [reviewComment, setReviewComment] = useState<string>("");
  const [isSubmittingReview, setIsSubmittingReview] = useState<boolean>(false);
  const [ocrTextFilter, setOcrTextFilter] = useState<string>("");
  const [leftPanelTab, setLeftPanelTab] = useState<"ocr" | "json">("ocr");

  // Base API endpoint URL
  const API_BASE = "http://localhost:8000";

  // Mock initial data seeds for Demo fallback
  const MOCK_OCR_TEMPLATES = {
    invoice: "ACME Supplies LLC\nInvoice Number: INV-2026-987\nDate: 2026-06-05\nAmount Due: $120.50\nSubtotal: $120.50\nTax: $0.00\nTotal: $120.50",
    receipt: "COFFEE DELIGHT #441\nDate: 2026-06-05 14:32\nTRANS: 98172635\n1 LATTE MACCHIATO - $4.75\n1 BLUEBERRY MUFFIN - $3.50\n1 BOTTLED WATER - $2.25\nTOTAL: $11.35",
    statement: "GLOBE TRUST BANK\nAccount: 1234-5678-9012\nStarting Balance: $5,000.00\nEnding Balance: $5,450.00\nStatement Period: May 1 to May 31, 2026",
    contract: "SOFTWARE LICENSE AGREEMENT\nEffective Date: 2026-06-05\nParties: Acme Corp, GlobeTech Solutions\nTotal Value: $15,000.00",
    "purchase order": "ACME CORP - PURCHASE ORDER\nPO Number: PO-2026-441\nPO Date: 2026-06-05\nVendor: Office Depot Supply\nTotal PO Amount: $1,400.00",
    certificate: "CERTIFICATE OF COMPLETION\nThis is to certify that Leelanjan S has successfully completed the\nData Science Program.\nIssued on: 2026-06-05\nIssued by: PaceWisdom AI Academy\nDirector Signatory: Dr. Alice Johnson",
    passport: "REPUBLIC OF INDIA PASSPORT\nPassport Number: L1234567\nGiven Name: JOHN DOE\nNationality: INDIAN\nDate of Birth: 12/04/1998\nDate of Expiry: 12/04/2036",
    resume: "John Doe\nEmail: john.doe@email.com\nSkills: Python, TensorFlow, SQLAlchemy\nEducation: Bachelor of Science in AI (National University)\nExperience: 2 Years as Junior ML Engineer at TechCorp",
    "driving license": "DRIVING LICENSE\nLicense Number: DL-9928371\nFull Name: LEELANJAN S\nDate of Birth: 12/04/1998\nAddress: 123 MG Road, Bangalore, India\nExpiry Date: 12/04/2036",
    "medical report": "METROPOLITAN CLINIC\nPatient Report\nPatient Name: Jane Smith\nAge: 28\nDate: 2026-06-05\nDiagnosis: Mild Influenza\nAttending Doctor: Dr. Robert Carter",
    marksheet: "BOARD OF SECONDARY EDUCATION\nAcademic Marksheet\nStudent Name: Leelanjan S\nRoll Number: DS-2026-004\nInstitution: National University\nTotal Marks: 450\nGrade: A+"
  };

  const mockDocuments: Document[] = [];

  // Try checking local connection to backend to select Mode (API or Demo fallback)
  useEffect(() => {
    const checkBackend = async () => {
      let mode: "api" | "demo" = "demo";
      try {
        const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(1500) });
        if (res.status === 200 || res.status === 503) {
          console.log("Connected to local backend, using API Mode.");
          mode = "api";
        }
      } catch (err) {
        console.warn("FastAPI backend not responding, fallback to client-only Demo Mode.");
        mode = "demo";
      }
      
      setApiMode(mode);
      
      // Load auth state from localStorage if it exists
      const savedToken = localStorage.getItem("auth_token");
      if (savedToken) {
        setAuthToken(savedToken);
        setIsAuthenticated(true);
        const savedRole = localStorage.getItem("user_role") || "admin";
        const savedEmail = localStorage.getItem("user_email") || "reviewer@acme.com";
        setUserRole(savedRole);
        setUserEmail(savedEmail);
      }
    };
    checkBackend();
  }, []);

  // Sync documents and metrics
  useEffect(() => {
    if (!isAuthenticated) return;
    
    if (apiMode === "demo") {
      // Seed Demo Data if empty
      const localDocs = localStorage.getItem("demo_docs");
      if (!localDocs) {
        localStorage.setItem("demo_docs", JSON.stringify(mockDocuments));
        setDocuments(mockDocuments);
      } else {
        setDocuments(JSON.parse(localDocs));
      }
    } else {
      // Fetch documents from REST API
      fetchDocuments();
    }
  }, [isAuthenticated, apiMode]);

  // Recalculate metrics summary when documents list changes
  useEffect(() => {
    if (documents.length === 0) {
      setMetrics({
        total_runs: 0,
        completed_runs: 0,
        failed_runs: 0,
        review_needed_runs: 0,
        average_latency_ms: 0,
        total_cost: 0.0
      });
      return;
    }
    const completed = documents.filter(d => d.status === "completed").length;
    const review = documents.filter(d => d.status === "review_needed").length;
    const failed = documents.filter(d => d.status === "failed").length;
    const total = documents.length;
    
    // Average Latency Mock
    const totalLatency = documents.reduce((acc, curr) => acc + (curr.file_size / 100), 0) + 1200;
    const avgLatency = Math.round(totalLatency / total);
    
    // Token usage cost mock
    const cost = documents.reduce((acc, curr) => {
      if (curr.status === "completed" || curr.status === "review_needed") {
        return acc + 0.0015 * (curr.status === "completed" ? 1.2 : 0.8);
      }
      return acc;
    }, 0.0125);

    setMetrics({
      total_runs: total,
      completed_runs: completed,
      failed_runs: failed,
      review_needed_runs: review,
      average_latency_ms: avgLatency,
      total_cost: parseFloat(cost.toFixed(4))
    });
  }, [documents]);

  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${API_BASE}/documents`, {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        // Load details for each document to populate nested schemas
        const loadedDocs = await Promise.all(data.map(async (doc: Document) => {
          doc.fileUrl = `${API_BASE}/documents/${doc.id}/file`;
          try {
            const resResult = await fetch(`${API_BASE}/documents/${doc.id}/result`, {
              headers: { "Authorization": `Bearer ${authToken}` }
            });
            if (resResult.ok) {
              const resData = await resResult.json();
              doc.extracted_data = resData.data;
              doc.field_confidences = resData.confidence_scores;
            }
          } catch (e) {}
          return doc;
        }));
        setDocuments(loadedDocs);
      } else if (res.status === 401) {
        handleLogout();
      }
    } catch (err) {
      console.error("Failed to fetch documents: " + err);
    }
  };

  // Login handler
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError("");
    
    // Client-side format validations
    if (!loginEmail.includes("@")) {
      setLoginError("Please enter a valid email address");
      return;
    }
    if (loginPassword.length < 6) {
      setLoginError("Password must be at least 6 characters");
      return;
    }

    setIsLoggingIn(true);

    if (apiMode === "demo") {
      // Mock Login validation
      setTimeout(() => {
        setIsLoggingIn(false);
        setIsAuthenticated(true);
        // Map roles based on email
        let role = "user";
        if (loginEmail.startsWith("admin")) role = "admin";
        else if (loginEmail.startsWith("reviewer") || loginEmail.includes("test")) role = "reviewer";
        
        setUserRole(role);
        setUserEmail(loginEmail);
        localStorage.setItem("auth_token", "demo-token-12345");
        localStorage.setItem("user_role", role);
        localStorage.setItem("user_email", loginEmail);
      }, 800);
    } else {
      // Hit real API Login
      try {
        const res = await fetch(`${API_BASE}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: loginEmail, password: loginPassword })
        });
        if (res.ok) {
          const data = await res.json();
          setAuthToken(data.access_token);
          setUserRole(data.user.role);
          setUserEmail(data.user.email);
          setIsAuthenticated(true);
          localStorage.setItem("auth_token", data.access_token);
          localStorage.setItem("user_role", data.user.role);
          localStorage.setItem("user_email", data.user.email);
        } else {
          const err = await res.json();
          setLoginError(err.detail || "Authentication failed.");
        }
      } catch (err) {
        setLoginError("Could not connect to authentication servers.");
      } finally {
        setIsLoggingIn(false);
      }
    }
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setAuthToken("");
    setUserRole("user");
    setUserEmail("");
    localStorage.removeItem("auth_token");
    localStorage.removeItem("user_role");
    localStorage.removeItem("user_email");
    setActiveTab("dashboard");
    setSelectedDoc(null);
  };

  // Drag and drop handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      processFileUpload(e.target.files[0]);
    }
  };

  const processFileUpload = async (file: File) => {
    // Validate MIME types
    const allowed = ["application/pdf", "image/png", "image/jpeg", "image/tiff"];
    if (!allowed.includes(file.type)) {
      alert("Invalid format: " + file.type + ". Allowed formats: PDF, PNG, JPEG, TIFF.");
      return;
    }

    setUploadProgress({ filename: file.name, percent: 10 });

    // Simulate progress bar increments
    let currentPercent = 10;
    const interval = setInterval(() => {
      if (currentPercent < 90) {
        currentPercent += Math.floor(Math.random() * 15) + 5;
        setUploadProgress(prev => prev ? { ...prev, percent: Math.min(95, currentPercent) } : null);
      }
    }, 200);

    if (apiMode === "demo") {
      // Demo upload simulation
      setTimeout(() => {
        clearInterval(interval);
        setUploadProgress(null);
        
        // Append a new document mock
        const newId = uuidv4();
        let classif = "Invoice";
        const fn = file.name.toLowerCase();
        
        if (fn.includes("receipt")) classif = "Receipt";
        else if (fn.includes("statement") || fn.includes("bank")) classif = "Bank Statement";
        else if (fn.includes("contract") || fn.includes("agreement")) classif = "Contract";
        else if (fn.includes("po") || fn.includes("purchase")) classif = "Purchase Order";
        else if (fn.includes("certificate") || fn.includes("cert")) classif = "Certificate";
        else if (fn.includes("passport")) classif = "Passport";
        else if (fn.includes("resume") || fn.includes("cv")) classif = "Resume";
        else if (fn.includes("license")) classif = "Driving License";
        else if (fn.includes("medical") || fn.includes("report")) classif = "Medical Report";
        else if (fn.includes("marksheet") || fn.includes("transcript") || fn.includes("academic")) classif = "Marksheet";

        const newDoc: Document = {
          id: newId,
          name: file.name,
          storage_path: `raw/org_1/${newId}.${file.name.split(".").pop()}`,
          status: "processing",
          mime_type: file.type,
          file_size: file.size,
          confidence_score: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          doc_type_name: classif,
          extracted_data: {},
          validation_errors: [],
          fileUrl: URL.createObjectURL(file)
        };

        const updatedDocs = [newDoc, ...documents];
        setDocuments(updatedDocs);
        localStorage.setItem("demo_docs", JSON.stringify(updatedDocs));
        
        // Simulate background agent run completions
        setTimeout(() => {
          // Complete processing
          const docsAfterRun = updatedDocs.map(d => {
            if (d.id === newId) {
              let extData: Record<string, any> = {};
              let fieldConf: Record<string, number> = {};
              let valErrors: string[] = [];
              let conf = 0.90;

              if (classif === "Invoice") {
                conf = 0.96;
                extData = {
                  invoice_number: "INV-2026-987",
                  invoice_date: "2026-06-05",
                  vendor_name: "ACME Supplies LLC",
                  amount: 120.50
                };
                fieldConf = { invoice_number: 0.98, invoice_date: 0.95, vendor_name: 0.97, amount: 0.96 };
              } else if (classif === "Receipt") {
                conf = 0.74;
                extData = {
                  receipt_number: "98172635",
                  date: "2026-06-05",
                  vendor_name: "COFFEE DELIGHT #441",
                  total_amount: null
                };
                fieldConf = { receipt_number: 0.85, date: 0.90, vendor_name: 0.80, total_amount: 0.00 };
                valErrors = ["Required field 'total_amount' is missing"];
              } else if (classif === "Bank Statement") {
                conf = 0.65;
                extData = {
                  account_number: "1234-5678-9012",
                  statement_date: "2026-05-31",
                  starting_balance: 5000.00,
                  ending_balance: 5450.00
                };
                fieldConf = { account_number: 0.88, statement_date: 0.92, starting_balance: 0.75, ending_balance: 0.65 };
                valErrors = ["Financial summary discrepancy: ending balance does not match transactions calculation"];
              } else if (classif === "Contract") {
                conf = 0.92;
                extData = {
                  effective_date: "2026-06-05",
                  parties: "Acme Corp, GlobeTech Solutions",
                  total_value: 15000.00
                };
                fieldConf = { effective_date: 0.95, parties: 0.90, total_value: 0.92 };
              } else if (classif === "Purchase Order") {
                conf = 0.94;
                extData = {
                  po_number: "PO-2026-441",
                  po_date: "2026-06-05",
                  vendor_name: "Office Depot Supply",
                  total_amount: 1400.00
                };
                fieldConf = { po_number: 0.96, po_date: 0.93, vendor_name: 0.95, total_amount: 0.94 };
              } else if (classif === "Certificate") {
                conf = 0.97;
                extData = {
                  student_name: "Leelanjan S",
                  course_name: "Data Science Program",
                  issue_date: "2026-06-05",
                  organization: "PaceWisdom AI Academy",
                  signatory: "Dr. Alice Johnson"
                };
                fieldConf = { student_name: 0.99, course_name: 0.98, issue_date: 0.97, organization: 0.96, signatory: 0.95 };
              } else if (classif === "Passport") {
                conf = 0.98;
                extData = {
                  passport_number: "L1234567",
                  name: "JOHN DOE",
                  nationality: "INDIAN",
                  date_of_birth: "1998-04-12",
                  expiry_date: "2036-04-12"
                };
                fieldConf = { passport_number: 0.99, name: 0.98, nationality: 0.99, date_of_birth: 0.97, expiry_date: 0.97 };
              } else if (classif === "Resume") {
                conf = 0.95;
                extData = {
                  candidate_name: "John Doe",
                  email: "john.doe@email.com",
                  skills: "Python, TensorFlow, SQLAlchemy",
                  education: "Bachelor of Science in AI",
                  experience: "2 Years as Junior ML Engineer"
                };
                fieldConf = { candidate_name: 0.98, email: 0.99, skills: 0.92, education: 0.94, experience: 0.92 };
              } else if (classif === "Driving License") {
                conf = 0.96;
                extData = {
                  license_number: "DL-9928371",
                  full_name: "LEELANJAN S",
                  date_of_birth: "1998-04-12",
                  address: "123 MG Road, Bangalore, India",
                  expiry_date: "2036-04-12"
                };
                fieldConf = { license_number: 0.97, full_name: 0.98, date_of_birth: 0.96, address: 0.94, expiry_date: 0.95 };
              } else if (classif === "Medical Report") {
                conf = 0.94;
                extData = {
                  patient_name: "Jane Smith",
                  age: 28,
                  diagnosis: "Mild Influenza",
                  date: "2026-06-05",
                  doctor_name: "Dr. Robert Carter"
                };
                fieldConf = { patient_name: 0.96, age: 0.95, diagnosis: 0.94, date: 0.93, doctor_name: 0.92 };
              } else if (classif === "Marksheet") {
                conf = 0.97;
                extData = {
                  student_name: "Leelanjan S",
                  roll_number: "DS-2026-004",
                  institution: "National University",
                  total_marks: 450,
                  grade: "A+"
                };
                fieldConf = { student_name: 0.99, roll_number: 0.98, institution: 0.97, total_marks: 0.96, grade: 0.95 };
              } else {
                conf = 0.90;
                extData = {
                  field_1: "Dynamic Value 1",
                  field_2: "Dynamic Value 2",
                  field_3: "Dynamic Value 3"
                };
                fieldConf = { field_1: 0.90, field_2: 0.90, field_3: 0.90 };
              }

              d.status = conf < 0.80 ? "review_needed" : "completed";
              d.confidence_score = conf;
              d.extracted_data = extData;
              d.validation_errors = valErrors;
              d.field_confidences = fieldConf;
            }
            return d;
          });
          setDocuments(docsAfterRun);
          localStorage.setItem("demo_docs", JSON.stringify(docsAfterRun));
        }, 3000);

        setActiveTab("documents");
      }, 1500);
    } else {
      // Hit real API Upload
      try {
        const formData = new FormData();
        formData.append("file", file);
        
        const res = await fetch(`${API_BASE}/documents/upload`, {
          method: "POST",
          headers: { "Authorization": `Bearer ${authToken}` },
          body: formData
        });

        clearInterval(interval);
        setUploadProgress(null);

        if (res.ok) {
          fetchDocuments();
          setActiveTab("documents");
        } else {
          const err = await res.json();
          alert("Upload failed: " + err.detail);
        }
      } catch (err) {
        clearInterval(interval);
        setUploadProgress(null);
        alert("Server connection failed during upload.");
      }
    }
  };

  // Review submission
  const handleReviewSubmit = async (action: "accepted" | "rejected" | "edited") => {
    if (!selectedDoc) return;
    setIsSubmittingReview(true);

    if (apiMode === "demo") {
      setTimeout(() => {
        setIsSubmittingReview(false);
        // Map modifications back
        const updated = documents.map(d => {
          if (d.id === selectedDoc.id) {
            d.status = action === "rejected" ? "failed" : "completed";
            d.confidence_score = 1.0;
            if (action === "edited") {
              d.extracted_data = editingData;
              d.validation_errors = [];
            }
          }
          return d;
        });
        setDocuments(updated);
        localStorage.setItem("demo_docs", JSON.stringify(updated));
        setSelectedDoc(null);
        setActiveTab("review-queue");
      }, 800);
    } else {
      try {
        const payload: Record<string, any> = { action, comments: reviewComment };
        if (action === "edited") {
          payload.data = editingData;
        }

        const res = await fetch(`${API_BASE}/documents/${selectedDoc.id}/review`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${authToken}`
          },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          fetchDocuments();
          setSelectedDoc(null);
          setActiveTab("review-queue");
        } else {
          const err = await res.json();
          alert("Failed to submit review: " + err.detail);
        }
      } catch (err) {
        alert("Server communication error.");
      } finally {
        setIsSubmittingReview(false);
      }
    }
  };

  const handleDeleteDocument = async (id: string) => {
    if (!confirm("Are you sure you want to delete this document? This action cannot be undone.")) {
      return;
    }
    
    if (apiMode === "demo") {
      const updated = documents.filter(d => d.id !== id);
      setDocuments(updated);
      localStorage.setItem("demo_docs", JSON.stringify(updated));
      if (selectedDoc && selectedDoc.id === id) {
        setSelectedDoc(null);
      }
    } else {
      try {
        const res = await fetch(`${API_BASE}/documents/${id}`, {
          method: "DELETE",
          headers: { "Authorization": `Bearer ${authToken}` }
        });
        if (res.ok) {
          fetchDocuments();
          if (selectedDoc && selectedDoc.id === id) {
            setSelectedDoc(null);
          }
        } else {
          const err = await res.json();
          alert("Failed to delete document: " + err.detail);
        }
      } catch (err) {
        alert("Server connection error during deletion.");
      }
    }
  };

  const handleEditField = (field: string, val: any) => {
    setEditingData(prev => ({
      ...prev,
      [field]: val
    }));
  };

  // Helper uuid generator for demo fallback
  const uuidv4 = () => {
    return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c: any) =>
      (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)
    );
  };

  // Filter lists based on tab
  const getFilteredDocs = () => {
    if (activeTab === "review-queue") {
      return documents.filter(d => d.status === "review_needed");
    }
    return documents;
  };

  // Format date helper
  const formatDate = (isoStr: string) => {
    const d = new Date(isoStr);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  // Render Login Component
  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen flex-col justify-center bg-slate-50 py-12 px-6 lg:px-8 font-sans antialiased text-slate-900">
        <div className="sm:mx-auto sm:w-full sm:max-w-md">
          <div className="flex justify-center">
            <span className="text-3xl font-extrabold text-slate-800">
              DocIntel AI
            </span>
          </div>
          <h2 className="mt-6 text-center text-3xl font-bold tracking-tight text-slate-800">
            Sign in to Platform
          </h2>
          <p className="mt-2 text-center text-sm text-slate-500">
            {apiMode === "demo" ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-600 border border-emerald-100">
                Offline Mode Active (Mock Data Loaded)
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-600 border border-indigo-100">
                Connected to Server API
              </span>
            )}
          </p>
        </div>

        <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
          <div className="bg-white border border-slate-200 py-8 px-4 shadow-xl rounded-2xl sm:px-10">
            <form className="space-y-6" onSubmit={handleLogin}>
              <div>
                <label htmlFor="email" className="block text-sm font-semibold text-slate-700">
                  Email Address
                </label>
                <div className="mt-2">
                  <input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="username"
                    required
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    className="block w-full min-h-[48px] px-3.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-base"
                    placeholder="reviewer@acme.com"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-semibold text-slate-700">
                  Password
                </label>
                <div className="mt-2 relative">
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    required
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    className="block w-full min-h-[48px] pl-3.5 pr-12 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-base"
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-pressed={showPassword}
                    aria-label="Show password"
                    className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 focus:outline-none"
                  >
                    {showPassword ? (
                      <span className="text-xs font-medium">Hide</span>
                    ) : (
                      <span className="text-xs font-medium">Show</span>
                    )}
                  </button>
                </div>
              </div>

              {loginError && (
                <div className="rounded-xl bg-red-50 border border-red-200 p-4">
                  <div className="text-sm font-medium text-red-600">{loginError}</div>
                </div>
              )}

              <div>
                <button
                  type="submit"
                  disabled={isLoggingIn}
                  className="flex w-full justify-center min-h-[48px] items-center rounded-xl bg-indigo-600 text-base font-bold text-white shadow-md hover:bg-indigo-700 active:scale-[0.98] transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {isLoggingIn ? "Signing in..." : "Sign In"}
                </button>
              </div>
            </form>

            <div className="mt-6 border-t border-slate-200 pt-6">
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-slate-400 font-medium">Quick Credentials</span>
              </div>
              <div className="mt-4 grid grid-cols-1 gap-3 text-xs text-slate-600 text-center">
                <button 
                  onClick={() => {
                    setLoginEmail("reviewer@acme.com");
                    setLoginPassword("reviewer123");
                  }}
                  type="button"
                  className="p-2.5 rounded-xl border border-slate-200 bg-slate-50 hover:bg-slate-100 transition-all cursor-pointer text-left"
                >
                  <p className="font-bold text-slate-700">Reviewer (Demo Mode)</p>
                  <p className="mt-0.5 text-[10px] text-slate-500">Email: reviewer@acme.com / PW: reviewer123</p>
                </button>
                <button 
                  onClick={() => {
                    setLoginEmail("admin@acme.com");
                    setLoginPassword("admin123");
                  }}
                  type="button"
                  className="p-2.5 rounded-xl border border-slate-200 bg-slate-50 hover:bg-slate-100 transition-all cursor-pointer text-left"
                >
                  <p className="font-bold text-slate-700">Admin (Demo Mode)</p>
                  <p className="mt-0.5 text-[10px] text-slate-500">Email: admin@acme.com / PW: admin123</p>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Render Core Application View
  return (
    <div className="flex h-screen bg-slate-50 font-sans antialiased text-slate-900 overflow-hidden">
      {/* Sidebar Navigation */}
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col justify-between p-6">
        <div className="space-y-8">
          <div className="flex items-center gap-3">
            <span className="text-2xl font-extrabold text-slate-800">
              DocIntel AI
            </span>
          </div>

          <nav className="space-y-1">
            {[
              { id: "dashboard", label: "Dashboard Overview", icon: "📊" },
              { id: "upload", label: "Upload Documents", icon: "📤" },
              { id: "documents", label: "All Documents", icon: "📂" },
              { id: "review-queue", label: "Review Queue", icon: "⚖️", count: documents.filter(d => d.status === "review_needed").length }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => {
                  setSelectedDoc(null);
                  setActiveTab(tab.id);
                }}
                className={`w-full flex items-center justify-between px-4 py-3 rounded-xl font-medium text-sm transition-all cursor-pointer ${
                  activeTab === tab.id
                    ? "bg-slate-100 text-slate-900 border border-slate-200 shadow-sm"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                <span className="flex items-center gap-3">
                  <span>{tab.icon}</span>
                  {tab.label}
                </span>
                {tab.count !== undefined && tab.count > 0 && (
                  <span className="bg-slate-200 text-slate-800 text-[10px] font-bold px-2 py-0.5 rounded-full border border-slate-300">
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </nav>
        </div>

        {/* User Card */}
        <div className="border-t border-slate-200 pt-4">
          <div className="flex items-center gap-3 p-2 bg-slate-50 border border-slate-200 rounded-xl">
            <div className="h-9 w-9 rounded-full bg-slate-200 flex items-center justify-center font-bold text-slate-700">
              {userEmail.substring(0, 2).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-bold text-slate-800 truncate">{userEmail}</p>
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{userRole}</p>
            </div>
            <button
              onClick={handleLogout}
              className="text-slate-400 hover:text-slate-600 cursor-pointer p-1"
              title="Logout"
            >
              🚪
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Pane */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Banner showing offline status */}
        <header className="h-16 px-8 bg-white border-b border-slate-200 flex items-center justify-between">
          <h1 className="text-lg font-bold text-slate-800 capitalize flex items-center gap-2">
            {activeTab.replace("-", " ")}
          </h1>
          <div className="flex items-center gap-3">
            {apiMode === "demo" ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 border border-emerald-100">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                Demo Mode (Simulation Sandbox)
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700 border border-indigo-100">
                <span className="h-1.5 w-1.5 rounded-full bg-indigo-500"></span>
                API Connected
              </span>
            )}
          </div>
        </header>

        {/* Content Tabs */}
        <div className="flex-1 overflow-y-auto p-8">
          
          {/* TAB 1: DASHBOARD OVERVIEW */}
          {activeTab === "dashboard" && (
            <div className="space-y-8">
              {/* Stat grid */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                {[
                  { label: "Total Files Processed", val: metrics.total_runs, icon: "📄" },
                  { label: "Accuracy Success Rate", val: metrics.total_runs > 0 ? `${Math.round((metrics.completed_runs / metrics.total_runs) * 100)}%` : "0%", icon: "✅" },
                  { label: "Requires Review", val: metrics.review_needed_runs, icon: "⚖️" },
                  { label: "Total LLM Token Cost", val: `$${metrics.total_cost.toFixed(4)}`, icon: "💰" }
                ].map((stat, idx) => (
                  <div key={idx} className="bg-white border border-slate-200 p-6 rounded-2xl flex items-center justify-between shadow-sm">
                    <div className="space-y-2">
                      <p className="text-sm font-semibold text-slate-400">{stat.label}</p>
                      <p className="text-3xl font-extrabold text-slate-800">{stat.val}</p>
                    </div>
                    <div className="h-12 w-12 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-center text-xl">
                      {stat.icon}
                    </div>
                  </div>
                ))}
              </div>

              {/* Performance Charts mock */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="bg-white border border-slate-200 p-6 rounded-2xl space-y-4 shadow-sm">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">Agent Latency Breakdown (ms)</h3>
                  <div className="space-y-3 pt-2">
                    {[
                      { name: "OCR Node (pytesseract)", ms: 450, color: "bg-slate-600" },
                      { name: "Classification Node (gpt-4o-mini)", ms: 320, color: "bg-slate-500" },
                      { name: "Extraction Node (gpt-4o-mini)", ms: 850, color: "bg-slate-700" },
                      { name: "Validation Node (program checks)", ms: 40, color: "bg-slate-400" },
                      { name: "Confidence Scorer (gpt-4o-mini)", ms: 380, color: "bg-slate-800" }
                    ].map((step, idx) => (
                      <div key={idx} className="space-y-1.5">
                        <div className="flex justify-between text-xs font-semibold">
                          <span className="text-slate-600">{step.name}</span>
                          <span className="text-slate-800">{step.ms} ms</span>
                        </div>
                        <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                          <div className={`h-full ${step.color} rounded-full`} style={{ width: `${(step.ms / 900) * 100}%` }}></div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-white border border-slate-200 p-6 rounded-2xl space-y-4 flex flex-col justify-between shadow-sm">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">Routing Outcomes</h3>
                  <div className="flex items-center justify-around py-4 flex-1">
                    {/* SVG Circular chart */}
                    <div className="relative h-36 w-36 flex items-center justify-center">
                      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                        <path className="text-slate-100" strokeWidth="3" stroke="currentColor" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                        <path className="text-slate-700" strokeDasharray={`${metrics.total_runs > 0 ? (metrics.completed_runs / metrics.total_runs) * 100 : 0}, 100`} strokeWidth="3.2" strokeLinecap="round" stroke="currentColor" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                      </svg>
                      <div className="absolute text-center">
                        <p className="text-2xl font-extrabold text-slate-800">{metrics.total_runs > 0 ? `${Math.round((metrics.completed_runs / metrics.total_runs) * 100)}%` : "0%"}</p>
                        <p className="text-[10px] font-semibold text-slate-400 uppercase">Auto-Passed</p>
                      </div>
                    </div>
                    
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                        <span className="h-3 w-3 rounded-full bg-slate-700"></span>
                        <span>Auto-Completed (Score ≥ 0.8)</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                        <span className="h-3 w-3 rounded-full bg-slate-400"></span>
                        <span>Review Queue (Score &lt; 0.8)</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                        <span className="h-3 w-3 rounded-full bg-red-400"></span>
                        <span>Failed processing</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: UPLOAD DOCUMENTS */}
          {activeTab === "upload" && (
            <div className="max-w-2xl mx-auto space-y-6">
              <div
                onDragEnter={handleDrag}
                onDragOver={handleDrag}
                onDragLeave={handleDrag}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-2xl p-12 text-center transition-all cursor-pointer flex flex-col items-center justify-center gap-4 ${
                  dragActive
                    ? "border-indigo-600 bg-indigo-50/50 scale-[0.99]"
                    : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50 shadow-sm"
                }`}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  className="hidden"
                  accept="application/pdf,image/png,image/jpeg,image/tiff"
                />
                <div className="h-16 w-16 rounded-full bg-slate-50 border border-slate-200 flex items-center justify-center text-3xl">
                  📥
                </div>
                <div className="space-y-1">
                  <p className="text-base font-bold text-slate-700">Drag and drop file here, or click to browse</p>
                  <p className="text-xs text-slate-400">Supports PDF, PNG, JPEG, TIFF up to 10MB</p>
                </div>
              </div>

              {uploadProgress && (
                <div className="bg-white border border-slate-200 p-6 rounded-2xl space-y-3 shadow-sm">
                  <div className="flex justify-between items-center text-sm font-semibold">
                    <span className="text-slate-700 truncate max-w-xs">{uploadProgress.filename}</span>
                    <span className="text-indigo-600">{uploadProgress.percent}%</span>
                  </div>
                  <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-600 transition-all duration-300" style={{ width: `${uploadProgress.percent}%` }}></div>
                  </div>
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Uploading to MinIO raw bucket...</p>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: ALL DOCUMENTS & TAB 4: REVIEW QUEUE */}
          {(activeTab === "documents" || activeTab === "review-queue") && !selectedDoc && (
            <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-md">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50/75 text-xs font-bold uppercase tracking-wider text-slate-500">
                      <th className="py-4 px-6">Document Name</th>
                      <th className="py-4 px-6">Classification</th>
                      <th className="py-4 px-6">Uploaded At</th>
                      <th className="py-4 px-6">Confidence Score</th>
                      <th className="py-4 px-6">Processing Status</th>
                      <th className="py-4 px-6 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-sm">
                    {getFilteredDocs().length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-12 text-center text-slate-400 font-medium">
                          No documents found in this queue.
                        </td>
                      </tr>
                    ) : (
                      getFilteredDocs().map((doc) => (
                        <tr key={doc.id} className="hover:bg-slate-50/55 hover:bg-slate-50/50 transition-all">
                          <td className="py-4 px-6 font-bold text-slate-800">{doc.name}</td>
                          <td className="py-4 px-6 font-semibold text-slate-600">{doc.doc_type_name || "Unclassified"}</td>
                          <td className="py-4 px-6 text-slate-500">{formatDate(doc.created_at)}</td>
                          <td className="py-4 px-6">
                            {doc.confidence_score !== null ? (
                              <span className={`font-extrabold ${doc.confidence_score >= 0.80 ? "text-emerald-600" : "text-amber-600"}`}>
                                {Math.round(doc.confidence_score * 100)}%
                              </span>
                            ) : (
                              <span className="text-slate-300">—</span>
                            )}
                          </td>
                          <td className="py-4 px-6">
                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold ${
                              doc.status === "completed" ? "bg-emerald-50 text-emerald-700 border border-emerald-100" :
                              doc.status === "review_needed" ? "bg-amber-50 text-amber-700 border border-amber-100" :
                              doc.status === "processing" ? "bg-indigo-50 text-indigo-700 border border-indigo-100" :
                              doc.status === "failed" ? "bg-red-50 text-red-700 border border-red-100" : "bg-slate-50 text-slate-600 border border-slate-100"
                            }`}>
                              <span className={`h-1.5 w-1.5 rounded-full ${
                                doc.status === "completed" ? "bg-emerald-500" :
                                doc.status === "review_needed" ? "bg-amber-500" :
                                doc.status === "processing" ? "bg-indigo-500 animate-pulse" : "bg-red-500"
                              }`}></span>
                              {doc.status.replace("_", " ")}
                            </span>
                          </td>
                          <td className="py-4 px-6 text-right">
                            <div className="flex justify-end gap-2">
                              {doc.status === "review_needed" ? (
                                <button
                                  onClick={() => {
                                    setSelectedDoc(doc);
                                    setEditingData(doc.extracted_data || {});
                                    setReviewComment("");
                                  }}
                                  className="px-3.5 py-1.5 rounded-lg bg-slate-800 text-white font-bold text-xs cursor-pointer hover:bg-slate-700 active:scale-95 transition-all border border-transparent"
                                >
                                  Audit Extract
                                </button>
                              ) : (
                                <button
                                  onClick={() => {
                                    setSelectedDoc(doc);
                                    setEditingData(doc.extracted_data || {});
                                    setReviewComment("");
                                  }}
                                  className="px-3.5 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-700 font-semibold text-xs cursor-pointer transition-all"
                                >
                                  View Metadata
                                </button>
                              )}
                              <button
                                onClick={() => handleDeleteDocument(doc.id)}
                                className="px-3.5 py-1.5 rounded-lg border border-red-200 hover:bg-red-50 text-red-600 font-semibold text-xs cursor-pointer transition-all active:scale-95 flex items-center justify-center"
                                title="Delete Document"
                              >
                                🗑️
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* DOCUMENT DETAIL / REVIEW SPLIT VIEW */}
          {selectedDoc && (
            <div className="flex flex-col h-full space-y-6">
              {/* Top backbar */}
              <div className="flex items-center justify-between">
                <div className="flex gap-2">
                  <button
                    onClick={() => setSelectedDoc(null)}
                    className="px-4 py-2 border border-slate-200 bg-white rounded-xl hover:bg-slate-50 text-slate-700 text-sm font-semibold transition-all cursor-pointer shadow-sm"
                  >
                    ← Return to Documents
                  </button>
                  <button
                    onClick={() => handleDeleteDocument(selectedDoc.id)}
                    className="px-4 py-2 border border-red-200 bg-white rounded-xl hover:bg-red-50 text-red-600 text-sm font-semibold transition-all cursor-pointer shadow-sm active:scale-95 flex items-center gap-1.5"
                  >
                    <span>🗑️</span> Delete Document
                  </button>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-slate-400">Confidence Rating:</span>
                  <span className={`text-lg font-extrabold ${selectedDoc.confidence_score && selectedDoc.confidence_score >= 0.80 ? "text-emerald-600" : "text-amber-600"}`}>
                    {selectedDoc.confidence_score ? `${Math.round(selectedDoc.confidence_score * 100)}%` : "N/A"}
                  </span>
                </div>
              </div>

              {/* Split Screen Layout */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 flex-1 overflow-hidden">
                <div className="bg-white border border-slate-200 rounded-2xl p-6 flex flex-col space-y-4 overflow-y-auto shadow-sm">
                  <div className="flex justify-between items-center border-b border-slate-100 pb-2 mb-1">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">Extraction Insights</h3>
                    <div className="flex gap-1 bg-slate-100 p-0.5 rounded-lg border border-slate-200">
                      <button
                        onClick={() => setLeftPanelTab("document")}
                        className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                          leftPanelTab === "document"
                            ? "bg-white text-slate-800 shadow-sm"
                            : "text-slate-500 hover:text-slate-800"
                        }`}
                      >
                        Original Doc
                      </button>
                      <button
                        onClick={() => setLeftPanelTab("ocr")}
                        className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                          leftPanelTab === "ocr"
                            ? "bg-white text-slate-800 shadow-sm"
                            : "text-slate-500 hover:text-slate-800"
                        }`}
                      >
                        Raw OCR Text
                      </button>
                      <button
                        onClick={() => setLeftPanelTab("json")}
                        className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                          leftPanelTab === "json"
                            ? "bg-white text-slate-800 shadow-sm"
                            : "text-slate-500 hover:text-slate-800"
                        }`}
                      >
                        JSON Payload
                      </button>
                    </div>
                  </div>
                  
                  {/* File Metadata info */}
                  <div className="flex gap-4 p-4 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-600">
                    <div>
                      <p className="font-bold text-slate-700">File Name</p>
                      <p className="mt-0.5 text-slate-800 truncate max-w-[140px]" title={selectedDoc.name}>{selectedDoc.name}</p>
                    </div>
                    <div>
                      <p className="font-bold text-slate-700">Format</p>
                      <p className="mt-0.5 text-slate-800 uppercase">{selectedDoc.mime_type.split("/")[1]}</p>
                    </div>
                    <div>
                      <p className="font-bold text-slate-700">File Size</p>
                      <p className="mt-0.5 text-slate-800">{Math.round(selectedDoc.file_size / 1024)} KB</p>
                    </div>
                  </div>

                  {leftPanelTab === "document" && (
                    <div className="flex-1 border border-slate-200 rounded-xl p-4 bg-slate-50 flex items-center justify-center min-h-[350px] max-h-[400px] overflow-hidden">
                      {selectedDoc.fileUrl ? (
                        selectedDoc.mime_type.startsWith("image/") ? (
                          <img
                            src={selectedDoc.fileUrl}
                            alt={selectedDoc.name}
                            className="max-w-full max-h-[330px] object-contain rounded-lg shadow-sm border border-slate-200"
                          />
                        ) : (
                          <iframe
                            src={selectedDoc.fileUrl}
                            title={selectedDoc.name}
                            className="w-full h-full min-h-[330px] border-0 rounded-lg"
                          />
                        )
                      ) : (
                        <div className="flex flex-col items-center justify-center p-8 text-center space-y-4 w-full h-full">
                          <div className="h-16 w-16 bg-slate-100 rounded-2xl flex items-center justify-center text-2xl border border-slate-200 text-slate-400">
                            📄
                          </div>
                          <div className="space-y-1">
                            <p className="text-sm font-bold text-slate-700">{selectedDoc.name}</p>
                            <p className="text-xs text-slate-400">Preview not loaded (API storage link offline)</p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {leftPanelTab === "ocr" && (
                    /* OCR Text highlight box */
                    <div className="flex-1 border border-slate-200 rounded-xl p-4 bg-slate-50 font-mono text-xs overflow-y-auto max-h-[400px]">
                      <div className="flex justify-between items-center pb-2 border-b border-slate-200 mb-3">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">OCR Output Text</span>
                        <input
                          type="text"
                          placeholder="Search text..."
                          value={ocrTextFilter}
                          onChange={(e) => setOcrTextFilter(e.target.value)}
                          className="bg-white border border-slate-200 rounded px-2 py-0.5 text-[10px] text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-300"
                        />
                      </div>
                      <pre className="whitespace-pre-wrap leading-relaxed text-slate-700">
                        {ocrTextFilter 
                          ? (MOCK_OCR_TEMPLATES[selectedDoc.doc_type_name?.toLowerCase() as keyof typeof MOCK_OCR_TEMPLATES] || MOCK_OCR_TEMPLATES.invoice)
                              .split("\n")
                              .map((line, i) => {
                                if (line.toLowerCase().includes(ocrTextFilter.toLowerCase())) {
                                  return <mark key={i} className="bg-yellow-100 text-yellow-800 block">{line}</mark>;
                                }
                                return <span key={i} className="block">{line}</span>;
                              })
                          : (MOCK_OCR_TEMPLATES[selectedDoc.doc_type_name?.toLowerCase() as keyof typeof MOCK_OCR_TEMPLATES] || MOCK_OCR_TEMPLATES.invoice)
                        }
                      </pre>
                    </div>
                  )}

                  {leftPanelTab === "json" && (
                    /* JSON Payload box */
                    <div className="flex-1 border border-slate-200 rounded-xl p-4 bg-slate-50 font-mono text-xs overflow-y-auto max-h-[400px]">
                      <div className="flex justify-between items-center pb-2 border-b border-slate-200 mb-3">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Database JSON Payload</span>
                        <button
                          onClick={() => navigator.clipboard.writeText(JSON.stringify(selectedDoc.extracted_data || {}, null, 2))}
                          className="bg-white border border-slate-200 rounded px-2 py-0.5 text-[10px] text-slate-700 font-bold hover:bg-slate-100 cursor-pointer active:scale-95 transition-all"
                        >
                          Copy JSON
                        </button>
                      </div>
                      <pre className="whitespace-pre-wrap leading-relaxed text-slate-700 overflow-x-auto text-[11px]">
                        {JSON.stringify(selectedDoc.extracted_data || {}, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>

                {/* Right Side: Fields Form Editor */}
                <div className="bg-white border border-slate-200 rounded-2xl p-6 flex flex-col space-y-6 overflow-y-auto shadow-sm">
                  <div className="space-y-1">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">Extracted Metadata Fields</h3>
                    <p className="text-xs text-slate-500">Review and correct fields before saving validation to databases</p>
                  </div>

                  {selectedDoc.validation_errors && selectedDoc.validation_errors.length > 0 && (
                    <div className="rounded-xl bg-amber-50 border border-amber-200 p-4 space-y-1">
                      <p className="text-xs font-bold text-amber-700 uppercase tracking-wider">Validation Warnings</p>
                      <ul className="list-disc list-inside text-xs text-slate-700 space-y-0.5">
                        {selectedDoc.validation_errors.map((err, idx) => (
                          <li key={idx}>{err}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Schema fields form inputs */}
                  <div className="space-y-4">
                    {Object.keys(editingData).length === 0 ? (
                      <p className="text-sm text-slate-400 italic">No structured data found.</p>
                    ) : (
                      Object.entries(editingData).map(([key, val]) => {
                        const score = selectedDoc.field_confidences?.[key] ?? 1.0;
                        return (
                          <div key={key} className="space-y-1.5">
                            <div className="flex justify-between items-center">
                              <label htmlFor={key} className="text-xs font-bold text-slate-600 capitalize">
                                {key.replace("_", " ")}
                              </label>
                              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                                score >= 0.85 ? "bg-emerald-50 text-emerald-700 border border-emerald-100" : "bg-amber-50 text-amber-700 border border-amber-100"
                              }`}>
                                Conf: {Math.round(score * 100)}%
                              </span>
                            </div>
                            <input
                              id={key}
                              type={typeof val === "number" ? "number" : "text"}
                              value={val ?? ""}
                              onChange={(e) => handleEditField(key, e.target.type === "number" ? parseFloat(e.target.value) : e.target.value)}
                              className="block w-full min-h-[48px] px-3.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300"
                            />
                          </div>
                        );
                      })
                    )}
                  </div>

                  {/* Review audit inputs */}
                  {selectedDoc.status === "review_needed" && (
                    <div className="space-y-4 border-t border-slate-100 pt-6 mt-6">
                      <div className="space-y-1.5">
                        <label htmlFor="comments" className="text-xs font-bold text-slate-600">
                          Auditing Notes / Comments
                        </label>
                        <textarea
                          id="comments"
                          value={reviewComment}
                          onChange={(e) => setReviewComment(e.target.value)}
                          placeholder="State reasoning for edits or rejection notes here..."
                          className="block w-full px-3.5 py-2 min-h-[80px] bg-slate-50 border border-slate-200 rounded-xl text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-slate-300"
                        />
                      </div>

                      {/* Action buttons */}
                      <div className="grid grid-cols-3 gap-3">
                        <button
                          onClick={() => handleReviewSubmit("rejected")}
                          disabled={isSubmittingReview}
                          className="flex justify-center items-center min-h-[48px] rounded-xl bg-red-50 hover:bg-red-100 border border-red-100 text-red-700 font-bold text-xs cursor-pointer active:scale-95 transition-all"
                        >
                          Reject Doc
                        </button>
                        <button
                          onClick={() => handleReviewSubmit("edited")}
                          disabled={isSubmittingReview}
                          className="flex justify-center items-center min-h-[48px] rounded-xl bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-700 font-bold text-xs cursor-pointer active:scale-95 transition-all"
                        >
                          Save Changes
                        </button>
                        <button
                          onClick={() => handleReviewSubmit("accepted")}
                          disabled={isSubmittingReview}
                          className="flex justify-center items-center min-h-[48px] rounded-xl bg-slate-800 hover:bg-slate-900 text-white font-bold text-xs cursor-pointer active:scale-95 transition-all"
                        >
                          Approve Doc
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

        </div>
      </main>
    </div>
  );
}
