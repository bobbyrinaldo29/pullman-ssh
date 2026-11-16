import { RedmineIssue, RedmineProject, RedmineQuery, RedmineUser } from '../types'

export function getSampleRedmineUser(): RedmineUser {
  return {
    id: 1,
    login: 'dev.lead',
    firstname: 'Dev',
    lastname: 'Engineer',
    mail: 'dev@company.com'
  }
}

export function getSampleRedmineProjects(): RedmineProject[] {
  return [
    {
      id: 101,
      name: 'Core Infrastructure & Deployment',
      identifier: 'core-infra',
      description: 'SSH, Docker, and Kubernetes deployment pipelines',
      is_public: true
    },
    {
      id: 102,
      name: 'Pullman Remote Editor',
      identifier: 'pullman-editor',
      description: 'Monaco code editor with remote SFTP file synchronization',
      is_public: true
    },
    {
      id: 103,
      name: 'Database Management Services',
      identifier: 'db-manager',
      description: 'MariaDB / MySQL query execution engine',
      is_public: false
    }
  ]
}

export function getSampleRedmineIssues(): RedmineIssue[] {
  return [
    {
      id: 1401,
      project: { id: 102, name: 'Pullman Remote Editor' },
      tracker: { id: 1, name: 'Bug' },
      status: { id: 1, name: 'New' },
      priority: { id: 4, name: 'Urgent' },
      author: { id: 1, name: 'Dev Engineer' },
      assigned_to: { id: 1, name: 'Dev Engineer' },
      subject: 'Fix Monaco editor cursor offset on remote UTF-8 file save',
      description:
        'When saving a remote file via SFTP containing multi-byte UTF-8 symbols, the cursor jumps to the beginning of the line.',
      done_ratio: 20,
      created_on: new Date(Date.now() - 3600000 * 4).toISOString(),
      updated_on: new Date(Date.now() - 3600000 * 2).toISOString(),
      journals: [
        {
          id: 1,
          user: { id: 1, name: 'Dev Engineer' },
          notes:
            'Investigated: the issue relates to buffer encoding discrepancy during write stream flush.',
          created_on: new Date(Date.now() - 3600000 * 2).toISOString()
        }
      ]
    },
    {
      id: 1402,
      project: { id: 101, name: 'Core Infrastructure & Deployment' },
      tracker: { id: 2, name: 'Feature' },
      status: { id: 2, name: 'In Progress' },
      priority: { id: 3, name: 'High' },
      author: { id: 2, name: 'Sys Admin' },
      assigned_to: { id: 1, name: 'Dev Engineer' },
      subject: 'Implement SSH key authentication with passphrase prompt',
      description:
        'Allow users to load encrypted ed25519 and RSA private keys and prompt for passphrase securely in dialog.',
      done_ratio: 60,
      created_on: new Date(Date.now() - 86400000 * 2).toISOString(),
      updated_on: new Date(Date.now() - 3600000 * 5).toISOString()
    },
    {
      id: 1403,
      project: { id: 102, name: 'Pullman Remote Editor' },
      tracker: { id: 4, name: 'Task' },
      status: { id: 3, name: 'Resolved' },
      priority: { id: 2, name: 'Normal' },
      author: { id: 1, name: 'Dev Engineer' },
      assigned_to: { id: 1, name: 'Dev Engineer' },
      subject: 'Add Redmine REST API issue tracker view',
      description:
        'Create an authentic web-styled Redmine interface for tracking tickets, bugs and tasks directly inside Pullman.',
      done_ratio: 100,
      created_on: new Date(Date.now() - 86400000 * 3).toISOString(),
      updated_on: new Date().toISOString()
    },
    {
      id: 1404,
      project: { id: 103, name: 'Database Management Services' },
      tracker: { id: 1, name: 'Bug' },
      status: { id: 4, name: 'Feedback' },
      priority: { id: 3, name: 'High' },
      author: { id: 3, name: 'QA Team' },
      assigned_to: { id: 1, name: 'Dev Engineer' },
      subject: 'Handle auto-reconnect on MySQL server idle timeout 28800s',
      description:
        'Verify if active query tab automatically refreshes connection when MariaDB closes socket.',
      done_ratio: 75,
      created_on: new Date(Date.now() - 86400000 * 4).toISOString(),
      updated_on: new Date(Date.now() - 86400000).toISOString()
    }
  ]
}

export function getSampleRedmineQueries(): RedmineQuery[] {
  return [
    { id: 1, name: 'Assigned to me', is_public: false },
    { id: 2, name: 'Reported by me', is_public: false },
    { id: 3, name: 'Urgent & Immediate Bugs', is_public: true },
    { id: 4, name: 'Sprint Backlog', is_public: true }
  ]
}
