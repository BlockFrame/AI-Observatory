export default async function handler(req, res) {
  // Only allow POST requests
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { name, url, description } = req.body;

  if (!name || !url) {
    return res.status(400).json({ error: 'Tool name and URL are required' });
  }

  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPO || 'BlockFrame/wiredframe-radar';

  if (!token) {
    console.error('GITHUB_TOKEN is not configured in Vercel environment variables');
    return res.status(500).json({ error: 'Server misconfiguration: GitHub Token missing' });
  }

  try {
    const issueTitle = `New Tool Request: ${name}`;
    const issueBody = `### Tool Suggestion\n\n**Name:** ${name}\n**URL:** ${url}\n\n**Description/Reason:**\n${description || 'No description provided.'}\n\n---\n*Submitted via rAIdar Tools Directory*`;

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
        labels: ['tool-suggestion', 'enhancement']
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
    console.error('Error submitting tool suggestion:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
}
