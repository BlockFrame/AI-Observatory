export default async function handler(req, res) {
  // Only allow POST requests
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { type, title, description } = req.body;

  if (!type || !title || !description) {
    return res.status(400).json({ error: 'Type, title, and description are required' });
  }

  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPO || 'BlockFrame/wiredframe-radar';

  if (!token) {
    console.error('GITHUB_TOKEN is not configured in Vercel environment variables');
    return res.status(500).json({ error: 'Server misconfiguration: GitHub Token missing' });
  }

  try {
    const label = type === 'bug' ? 'bug' : 'enhancement';
    const typeLabel = type === 'bug' ? 'Bug Report' : 'Improvement Suggestion';
    const issueTitle = `[${typeLabel}] ${title}`;
    const issueBody = `### ${typeLabel}\n\n**Details:**\n${description}\n\n---\n*Submitted via Wiredframe Radar Feedback Modal*`;

    const response = await fetch(`https://api.github.com/repos/${repo}/issues`, {
      method: 'POST',
      headers: {
        'Authorization': `token ${token}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        title: issueTitle,
        body: issueBody,
        labels: ['feedback', label]
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`GitHub API error: ${response.status} ${response.statusText}`, errorText);
      return res.status(502).json({ error: 'Failed to create GitHub issue' });
    }

    const data = await response.json();
    
    return res.status(200).json({ 
      success: true, 
      issue_url: data.html_url 
    });
    
  } catch (error) {
    console.error('Error submitting feedback:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
}
