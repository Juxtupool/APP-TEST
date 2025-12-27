import requests
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class CommunityLibraryService:
    """
    Fetches community macros from GitHub repository.
    Allows browsing, searching, and downloading macros.
    """
    
    def __init__(self, config: Dict):
        """
        Args:
            config: Dictionary with github.community_repo configuration
        """
        self.repo = config.get('github', {}).get('community_repo', '')
        self.github_token = config.get('github', {}).get('token', None)
        
        # Base URLs
        if self.repo:
            self.api_base = f"https://api.github.com/repos/{self.repo}/contents"
            self.raw_base = f"https://raw.githubusercontent.com/{self.repo}/main"
        else:
            self.api_base = None
            self.raw_base = None
        
        # Cache for performance
        self._categories_cache = None
        self._macros_cache = {}
        
        logger.info(f"CommunityLibraryService initialized. Repo: {self.repo}")
    
    def _get_headers(self) -> Dict:
        """Get headers for GitHub API request."""
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Macropad-Pro'
        }
        
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        return headers
    
    def get_categories(self, force_refresh: bool = False) -> List[str]:
        """
        Get list of macro categories (subdirectories in macros/).
        
        Returns:
            List of category names (e.g., ['productivity', 'creative', 'gaming'])
        """
        if not self.api_base:
            return []
        
        if self._categories_cache and not force_refresh:
            return self._categories_cache
        
        try:
            url = f"{self.api_base}/macros"
            logger.info(f"Fetching categories from {url}")
            
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            
            if response.status_code == 404:
                logger.warning("Community repo or macros folder not found")
                return []
            
            response.raise_for_status()
            contents = response.json()
            
            # Filter directories only
            categories = [item['name'] for item in contents if item['type'] == 'dir']
            
            self._categories_cache = categories
            logger.info(f"Found categories: {categories}")
            
            return categories
            
        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []
    
    def get_macros_in_category(self, category: str, force_refresh: bool = False) -> List[Dict]:
        """
        Get all macros in a specific category.
        
        Args:
            category: Category name (e.g., 'productivity')
            force_refresh: Force refresh from GitHub (ignore cache)
        
        Returns:
            List of macro dictionaries with metadata and content
        """
        if not self.api_base or not self.raw_base:
            return []
        
        cache_key = category
        if cache_key in self._macros_cache and not force_refresh:
            return self._macros_cache[cache_key]
        
        try:
            url = f"{self.api_base}/macros/{category}"
            logger.info(f"Fetching macros from {url}")
            
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            
            files = response.json()
            macros = []
            
            # Filter JSON files and fetch their content
            for file in files:
                if file['type'] == 'file' and file['name'].endswith('.json'):
                    try:
                        # Fetch macro content from raw URL
                        macro_url = f"{self.raw_base}/macros/{category}/{file['name']}"
                        macro_response = requests.get(macro_url, headers=self._get_headers(), timeout=10)
                        macro_response.raise_for_status()
                        
                        macro_data = macro_response.json()
                        
                        # Add metadata
                        macro_data['_metadata'] = {
                            'category': category,
                            'filename': file['name'],
                            'download_url': macro_url,
                            'size': file.get('size', 0)
                        }
                        
                        macros.append(macro_data)
                        
                    except Exception as e:
                        logger.warning(f"Failed to fetch macro {file['name']}: {e}")
                        continue
            
            self._macros_cache[cache_key] = macros
            logger.info(f"Fetched {len(macros)} macros from {category}")
            
            return macros
            
        except Exception as e:
            logger.error(f"Error fetching macros in category {category}: {e}")
            return []
    
    def search_macros(self, query: str) -> List[Dict]:
        """
        Search macros across all categories.
        
        Args:
            query: Search term (searches in name, description, tags)
        
        Returns:
            List of matching macros
        """
        query_lower = query.lower()
        results = []
        
        categories = self.get_categories()
        
        for category in categories:
            macros = self.get_macros_in_category(category)
            
            for macro in macros:
                # Search in name
                if query_lower in macro.get('name', '').lower():
                    results.append(macro)
                    continue
                
                # Search in description
                if query_lower in macro.get('description', '').lower():
                    results.append(macro)
                    continue
                
                # Search in tags
                tags = macro.get('tags', [])
                if any(query_lower in tag.lower() for tag in tags):
                    results.append(macro)
        
        logger.info(f"Search '{query}' returned {len(results)} results")
        return results
    
    def get_all_macros(self, sort_by: str = 'name') -> List[Dict]:
        """
        Get all macros from all categories.
        
        Args:
            sort_by: Sort method ('name', 'category', 'date')
        
        Returns:
            List of all macros
        """
        all_macros = []
        categories = self.get_categories()
        
        for category in categories:
            macros = self.get_macros_in_category(category)
            all_macros.extend(macros)
        
        # Sort
        if sort_by == 'name':
            all_macros.sort(key=lambda x: x.get('name', '').lower())
        elif sort_by == 'category':
            all_macros.sort(key=lambda x: x.get('_metadata', {}).get('category', ''))
        
        logger.info(f"Retrieved {len(all_macros)} total macros")
        return all_macros
    
    def generate_submission_url(self, macro_data: Dict) -> str:
        """
        Generate a GitHub Issue URL for submitting a new macro.
        
        Args:
            macro_data: Macro JSON data
        
        Returns:
            Pre-filled GitHub Issue URL
        """
        if not self.repo:
            return ''
        
        import json
        import urllib.parse
        
        # Create issue title
        title = f"[Macro Submission] {macro_data.get('name', 'Unnamed Macro')}"
        
        # Create issue body with JSON payload
        body = f"""### Macro Submission

**Name:** {macro_data.get('name', '')}
**Description:** {macro_data.get('description', '')}
**Category:** {macro_data.get('category', 'productivity')}
**Tags:** {', '.join(macro_data.get('tags', []))}

### Macro JSON

```json
{json.dumps(macro_data, indent=2)}
```

---
*Submitted via Macropad Pro*
"""
        
        # Create issue URL
        base_url = f"https://github.com/{self.repo}/issues/new"
        params = {
            'title': title,
            'body': body,
            'labels': 'macro-submission'
        }
        
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        logger.info(f"Generated submission URL for '{macro_data.get('name')}'")
        return url
    
    def upload_macro(self, macro_data: Dict) -> Dict:
        """
        Uploads a macro to the GitHub repository directly.
        Requires github.token to be set in config.
        """
        if not self.repo or not self.github_token:
            return {"status": "error", "message": "Repository or Token not configured"}

        import base64
        import json
        
        try:
            category = macro_data.get('category', 'other').lower()
            name = macro_data.get('name', 'unnamed')
            # Sanitize filename
            safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
            filename = f"{safe_name}.json"
            path = f"macros/{category}/{filename}"
            
            url = f"https://api.github.com/repos/{self.repo}/contents/{path}"
            
            # Prepare content
            json_content = json.dumps(macro_data, indent=2)
            content_b64 = base64.b64encode(json_content.encode('utf-8')).decode('utf-8')
            
            # Check if file exists (to get SHA for update, or fail if we don't want to overwrite)
            # For now, let's assume new files only or handle update in future
            # But to be safe, we should check.
            get_resp = requests.get(url, headers=self._get_headers())
            sha = None
            if get_resp.status_code == 200:
                sha = get_resp.json().get('sha')
                
            payload = {
                "message": f"Added community macro: {name}",
                "content": content_b64
            }
            if sha:
                payload["sha"] = sha
                
            logger.info(f"Uploading macro to {path}...")
            response = requests.put(url, headers=self._get_headers(), json=payload, timeout=15)
            
            if response.status_code in [200, 201]:
                self.clear_cache() # Clear cache to show new macro
                logger.info("Upload successful")
                return {"status": "success", "path": path}
            else:
                try:
                    err_msg = response.json().get('message', response.text)
                except:
                    err_msg = response.text
                logger.error(f"GitHub API Error: {err_msg}")
                return {"status": "error", "message": f"GitHub Error: {err_msg}"}
                
        except Exception as e:
            logger.error(f"Upload exception: {e}")
            return {"status": "error", "message": str(e)}

    def clear_cache(self):
        """Clear the macro cache."""
        self._categories_cache = None
        self._macros_cache = {}
        logger.info("Cleared community library cache")
