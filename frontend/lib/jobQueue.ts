export type BackgroundJob = {
  uploadId: number;
  status: "processing" | "completed" | "completed_with_errors" | "failed";
  notified: boolean;
  startedAt: string;
};

const KEY = "vengage_bg_jobs";

export function getJobs(): BackgroundJob[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]") as BackgroundJob[];
  } catch {
    return [];
  }
}

export function addJob(uploadId: number): void {
  const jobs = getJobs().filter((j) => j.uploadId !== uploadId);
  jobs.unshift({ uploadId, status: "processing", notified: false, startedAt: new Date().toISOString() });
  localStorage.setItem(KEY, JSON.stringify(jobs.slice(0, 20)));
}

export function updateJob(uploadId: number, status: BackgroundJob["status"]): void {
  const jobs = getJobs().map((j) =>
    j.uploadId === uploadId ? { ...j, status } : j,
  );
  localStorage.setItem(KEY, JSON.stringify(jobs));
}

export function markNotified(uploadId: number): void {
  const jobs = getJobs().map((j) =>
    j.uploadId === uploadId ? { ...j, notified: true } : j,
  );
  localStorage.setItem(KEY, JSON.stringify(jobs));
}

export function clearJob(uploadId: number): void {
  localStorage.setItem(KEY, JSON.stringify(getJobs().filter((j) => j.uploadId !== uploadId)));
}

export function pendingCount(): number {
  return getJobs().filter((j) => j.status === "processing").length;
}

export function unnotifiedCount(): number {
  return getJobs().filter((j) => j.status !== "processing" && !j.notified).length;
}
