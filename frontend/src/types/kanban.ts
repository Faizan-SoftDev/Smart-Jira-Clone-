export interface BoardIssue {
  id: string;
  key: string;
  title: string;
  description: string;
  issue_type: string;
  priority: "lowest" | "low" | "medium" | "high" | "highest";
  status: string;
  status_name: string;
  assignee_user_id: string | null;
}

export interface BoardColumn {
  id: string;
  name: string;
  category: "todo" | "in_progress" | "done";
  issues: BoardIssue[];
}

export interface ProjectBoard {
  project_id: string;
  columns: BoardColumn[];
}
