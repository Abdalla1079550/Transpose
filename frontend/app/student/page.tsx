"use client";

import { useCallback, useMemo, useState } from "react";
import { CandidateCard } from "@/components/CandidateCard";
import { ErrorState } from "@/components/ErrorState";
import { SurfaceCard } from "@/components/SurfaceCard";
import {
  BACKEND_URL,
  createStudent,
  getInterviewQuestions,
  getStudentCard,
  submitInterview
} from "@/lib/api";
import type { CandidateCardData } from "@/lib/types";

type GenericRecord = Record<string, unknown>;

function asRecord(value: unknown): GenericRecord | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as GenericRecord;
  }
  return null;
}

function extractId(payload: GenericRecord): string | null {
  const direct = payload.id ?? payload.student_id ?? payload.uuid;
  if (typeof direct === "string" || typeof direct === "number") {
    return String(direct);
  }

  const nestedStudent = asRecord(payload.student);
  const nestedId = nestedStudent?.id ?? nestedStudent?.student_id;
  if (typeof nestedId === "string" || typeof nestedId === "number") {
    return String(nestedId);
  }

  return null;
}

function extractQuestions(payload: GenericRecord): string[] {
  const questions = payload.questions;
  if (Array.isArray(questions)) {
    return questions
      .map((item) => (typeof item === "string" ? item : ""))
      .filter(Boolean);
  }

  const items = payload.items;
  if (Array.isArray(items)) {
    return items
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }
        const record = asRecord(item);
        return typeof record?.question === "string" ? record.question : "";
      })
      .filter(Boolean);
  }

  return [];
}

function extractCard(payload: GenericRecord): CandidateCardData | null {
  const direct = asRecord(payload.card) || asRecord(payload.candidate_card);
  if (direct) {
    return direct as CandidateCardData;
  }
  if (Object.keys(payload).length > 0) {
    return payload as CandidateCardData;
  }
  return null;
}

export default function StudentPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [location, setLocation] = useState("");
  const [gradYear, setGradYear] = useState("");
  const [targetRole, setTargetRole] = useState("data_analyst");
  const [skills, setSkills] = useState("");
  const [cvFile, setCvFile] = useState<File | null>(null);

  const [studentId, setStudentId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<string[]>([]);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [candidateCard, setCandidateCard] = useState<CandidateCardData | null>(null);

  const [uploadError, setUploadError] = useState<string | null>(null);
  const [interviewError, setInterviewError] = useState<string | null>(null);
  const [cardError, setCardError] = useState<string | null>(null);

  const [uploading, setUploading] = useState(false);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [submittingInterview, setSubmittingInterview] = useState(false);
  const [loadingCard, setLoadingCard] = useState(false);

  const uploadStudent = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setUploadError(null);
    setInterviewError(null);
    setCardError(null);
    setCandidateCard(null);

    const formData = new FormData();
    formData.append("full_name", fullName);
    formData.append("email", email);
    formData.append("location", location);
    formData.append("grad_year", gradYear);
    formData.append("target_role", targetRole);
    formData.append("skills", skills);
    if (cvFile) {
      formData.append("cv", cvFile);
      formData.append("cv_file", cvFile);
    }

    setUploading(true);
    const result = await createStudent(formData);
    setUploading(false);

    if (!result.ok) {
      setUploadError(result.error);
      return;
    }

    const id = extractId(result.data);
    if (!id) {
      setUploadError("Student created but no student id returned by backend.");
      return;
    }

    setStudentId(id);
  };

  const loadQuestions = useCallback(async () => {
    if (!studentId) {
      setInterviewError("Upload your profile first to begin interview calibration.");
      return;
    }

    setInterviewError(null);
    setLoadingQuestions(true);
    const result = await getInterviewQuestions(targetRole);
    setLoadingQuestions(false);

    if (!result.ok) {
      setInterviewError(result.error);
      return;
    }

    const extracted = extractQuestions(result.data);
    if (extracted.length === 0) {
      setInterviewError("No interview questions were returned for this role cluster.");
      return;
    }

    setQuestions(extracted);
    setAnswers({});
  }, [studentId, targetRole]);

  const loadCandidateCard = useCallback(async () => {
    if (!studentId) {
      setCardError("Student id is missing. Upload profile first.");
      return;
    }

    setCardError(null);
    setLoadingCard(true);
    const result = await getStudentCard(studentId);
    setLoadingCard(false);

    if (!result.ok) {
      setCardError(result.error);
      return;
    }

    const card = extractCard(result.data);
    if (!card) {
      setCardError("Candidate card payload was empty.");
      return;
    }

    setCandidateCard(card);
  }, [studentId]);

  const sendInterview = async () => {
    if (!studentId) {
      setInterviewError("Student id is missing. Upload profile first.");
      return;
    }

    if (questions.length === 0) {
      setInterviewError("Load interview questions before submitting answers.");
      return;
    }

    setInterviewError(null);
    setSubmittingInterview(true);

    const payload = {
      role_cluster: targetRole,
      answers: questions.map((question, index) => ({
        question,
        answer: answers[index] || ""
      }))
    };

    const result = await submitInterview(studentId, payload);
    setSubmittingInterview(false);

    if (!result.ok) {
      setInterviewError(result.error);
      return;
    }

    await loadCandidateCard();
  };

  const completionRatio = useMemo(() => {
    if (questions.length === 0) {
      return "0/0";
    }
    const completed = questions.reduce((count, _, index) => {
      return answers[index]?.trim() ? count + 1 : count;
    }, 0);
    return `${completed}/${questions.length}`;
  }, [answers, questions]);

  return (
    <div className="page-stack">
      <section className="page-header">
        <div>
          <p className="eyebrow">Student Workflow</p>
          <h1 className="page-title">Upload CV, complete interview, generate candidate card</h1>
        </div>
      </section>

      <SurfaceCard title="1. Candidate Intake" subtitle={`Backend: ${BACKEND_URL}`}>
        <form className="form-grid" onSubmit={uploadStudent}>
          <label className="field">
            Full name
            <input
              required
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder="Avery Jordan"
            />
          </label>
          <label className="field">
            Email
            <input
              required
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="avery@school.edu"
            />
          </label>
          <label className="field">
            Location
            <input
              value={location}
              onChange={(event) => setLocation(event.target.value)}
              placeholder="New York, NY"
            />
          </label>
          <label className="field">
            Grad year
            <input
              value={gradYear}
              onChange={(event) => setGradYear(event.target.value)}
              placeholder="2026"
            />
          </label>
          <label className="field">
            Target role
            <input
              value={targetRole}
              onChange={(event) => setTargetRole(event.target.value)}
              placeholder="data_analyst"
            />
          </label>
          <label className="field field-span-2">
            Skills (comma separated)
            <input
              value={skills}
              onChange={(event) => setSkills(event.target.value)}
              placeholder="SQL, Python, Product Analytics"
            />
          </label>
          <label className="field field-span-2">
            CV upload
            <input
              type="file"
              accept=".pdf,.doc,.docx,.txt"
              onChange={(event) => setCvFile(event.target.files?.[0] || null)}
            />
          </label>
          <button className="primary-button" type="submit" disabled={uploading}>
            {uploading ? "Uploading…" : "Upload Candidate"}
          </button>
        </form>

        {studentId && <p className="success-line">Student ID: {studentId}</p>}
        {uploadError && <ErrorState compact message={uploadError} onRetry={() => setUploadError(null)} />}
      </SurfaceCard>

      <SurfaceCard
        title="2. Interview Calibration"
        subtitle={`Answer completion: ${completionRatio}`}
        actions={
          <button className="secondary-button" type="button" onClick={loadQuestions} disabled={loadingQuestions}>
            {loadingQuestions ? "Loading…" : "Load Questions"}
          </button>
        }
      >
        {!studentId && <p className="muted-copy">Upload candidate details to unlock interview stage.</p>}

        {questions.length > 0 && (
          <div className="question-stack">
            {questions.map((question, index) => (
              <label key={`${index}-${question}`} className="field">
                Q{index + 1}. {question}
                <textarea
                  rows={3}
                  value={answers[index] || ""}
                  onChange={(event) =>
                    setAnswers((prev) => ({
                      ...prev,
                      [index]: event.target.value
                    }))
                  }
                  placeholder="Add concise, evidence-based answer"
                />
              </label>
            ))}
            <button className="primary-button" type="button" onClick={sendInterview} disabled={submittingInterview}>
              {submittingInterview ? "Submitting…" : "Submit Interview"}
            </button>
          </div>
        )}

        {interviewError && <ErrorState compact message={interviewError} onRetry={loadQuestions} />}
      </SurfaceCard>

      <SurfaceCard
        title="3. Candidate Card"
        subtitle="Structured profile generated from CV + interview"
        actions={
          <button className="secondary-button" type="button" onClick={loadCandidateCard} disabled={loadingCard}>
            {loadingCard ? "Loading…" : "Refresh Card"}
          </button>
        }
      >
        {!candidateCard && !cardError && <p className="muted-copy">Candidate card will appear after interview submission.</p>}
        {cardError && <ErrorState compact message={cardError} onRetry={loadCandidateCard} />}
        {candidateCard && <CandidateCard card={candidateCard} />}
      </SurfaceCard>
    </div>
  );
}
