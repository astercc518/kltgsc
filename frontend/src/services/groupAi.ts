import api from './api';

export interface InboxRow {
  id: number; status: string; reply_text: string | null;
  chat_id: number; source_user_id: number; source_text: string;
  sent_at: string | null; created_at: string;
  solution_topic: string | null; extracted_needs: string[] | null;
}

export const groupAiAdminApi = {
  listInbox: (customer_id: number) =>
    api.get<InboxRow[]>(`/inbox/group-ai/customers/${customer_id}/recent`).then(r => r.data),
  approveSuggested: (pr_id: number) =>
    api.post(`/inbox/group-ai/suggested/${pr_id}/approve`),
  editSuggested: (pr_id: number, reply_text: string) =>
    api.put(`/inbox/group-ai/suggested/${pr_id}`, { reply_text }),
};
