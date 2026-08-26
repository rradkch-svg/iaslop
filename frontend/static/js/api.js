const API_BASE = "";

export const API = {
  async getVoices() {
    const res = await fetch(`${API_BASE}/api/voices`);
    return await res.json();
  },

  async getFormats() {
    const res = await fetch(`${API_BASE}/api/formats`);
    return await res.json();
  },

  async getGenres() {
    const res = await fetch(`${API_BASE}/api/genres`);
    return await res.json();
  },

  async generateTopics(count = 3) {
    const res = await fetch(`${API_BASE}/api/topics/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ count })
    });
    return await res.json();
  },

  async getApiKeys() {
    const res = await fetch(`${API_BASE}/api/settings/keys`);
    return await res.json();
  },

  async saveApiKeys(keys) {
    const res = await fetch(`${API_BASE}/api/settings/keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(keys)
    });
    const data = await res.json();
    return data;
  },

  // YouTube Data API
  async getYoutubeStatus() {
    const res = await fetch(`${API_BASE}/api/youtube/status`);
    return await res.json();
  },

  async uploadYoutubeClientSecrets(formData) {
    const res = await fetch(`${API_BASE}/api/youtube/client-secrets`, {
      method: "POST",
      body: formData
    });
    return await res.json();
  },

  async authYoutubeDesktop() {
    const res = await fetch(`${API_BASE}/api/youtube/auth/desktop`, {
      method: "POST"
    });
    return await res.json();
  },

  async uploadToYoutube(projectId, { title, description, tags, privacy_status, category_id }) {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/youtube/upload`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, description, tags, privacy_status, category_id })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Falha no upload do YouTube");
    return data;
  },

  async getProjects() {
    const res = await fetch(`${API_BASE}/api/projects`);
    return await res.json();
  },

  async createProject(topic) {
    const res = await fetch(`${API_BASE}/api/projects/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, video_format: "shorts_9_16" })
    });
    return await res.json();
  },

  async getProject(id) {
    const res = await fetch(`${API_BASE}/api/projects/${id}`);
    if (!res.ok) throw new Error("Project not found");
    return await res.json();
  },

  // 1-Click Multi-Agent AutoPilot
  async triggerAutoPilot(data) {
    const res = await fetch(`${API_BASE}/api/autopilot`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
    return await res.json();
  },

  // Batch Routines API
  async startBatchRoutine(data) {
    const res = await fetch(`${API_BASE}/api/routines/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result.error || "Erro ao iniciar rotina");
    return result;
  },

  async getRoutineStatus() {
    const res = await fetch(`${API_BASE}/api/routines/status`);
    return await res.json();
  }
};
