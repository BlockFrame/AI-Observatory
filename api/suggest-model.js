export default async function handler(req, res) {
  // Only allow POST requests
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { name, maker, url, description } = req.body;

  if (!name || !maker) {
    return res.status(400).json({ error: 'Model name and maker/provider are required' });
  }

  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPO || 'BlockFrame/wiredframe-radar';

  if (!token) {
    console.error('GITHUB_TOKEN is not configured in Vercel environment variables');
    return res.status(500).json({ error: 'Server misconfiguration: GitHub Token missing' });
  }

  try {
    const issueTitle = `New Model Suggestion: ${name} (${maker})`;
    const issueBody = `### Model Suggestion\n\n**Model Name:** ${name}\n**Maker / Provider:** ${maker}\n**Link / URL:** ${url || 'Not provided'}\n\n**Details / Description:**\n${description || 'No description provided.'}\n\n---\n*Submitted via rAIdar Models Directory*`;

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
        labels: ['model-suggestion', 'enhancement']
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
    console.error('Error submitting model suggestion:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
}
