import requests
import logging
from typing import Dict, List, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        self.config = config
        self.repo = config.get('github', {}).get('community_repo', '')
        self.github_token = config.get('github', {}).get('token', None)
        
        # Base URLs
        if self.repo:
            self.api_base = f"https://api.github.com/repos/{self.repo}/contents"
            self.raw_base = f"https://raw.githubusercontent.com/{self.repo}/main"
        else:
            self.api_base = None
            self.raw_base = None
        
        # Set up a requests.Session with connection pooling for concurrent requests
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=15, pool_maxsize=30)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # Cache for performance
        self._categories_cache = None
        self._macros_cache = {}
        
        # New attributes from the change
        self._window = None  # Reference to main window
        self._last_update = 0 # Timestamp of last fetch
        self._cache_ttl = 300 # 5 minutes cache
        
        logger.info(f"CommunityLibraryService initialized. Repo: {self.repo}")
    
    def set_window(self, window):
        """Set the window reference."""
        self._window = window
    
    def _get_headers(self) -> Dict:
        """Get headers for GitHub API request."""
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Overcontrol'
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
            
            response = self.session.get(url, headers=self._get_headers(), timeout=10)
            
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
    
    def _fetch_single_macro(self, category: str, file: Dict) -> Optional[Dict]:
        """
        Fetch a single macro from raw content URL.
        Designed to run in thread pool.
        """
        try:
            macro_url = f"{self.raw_base}/macros/{category}/{file['name']}"
            macro_response = self.session.get(macro_url, headers=self._get_headers(), timeout=10)
            macro_response.raise_for_status()
            
            macro_data = macro_response.json()
            
            # Add metadata
            macro_data['_metadata'] = {
                'category': category,
                'filename': file['name'],
                'download_url': macro_url,
                'size': file.get('size', 0)
            }
            return macro_data
        except Exception as e:
            logger.warning(f"Failed to fetch macro {file['name']}: {e}")
            return None
            
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
            logger.info(f"Fetching macros listing from {url}")
            
            response = self.session.get(url, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            
            files = response.json()
            json_files = [f for f in files if f['type'] == 'file' and f['name'].endswith('.json')]
            macros = []
            
            if json_files:
                # Use ThreadPoolExecutor to fetch raw content concurrently
                with ThreadPoolExecutor(max_workers=min(10, len(json_files))) as executor:
                    future_to_file = {
                        executor.submit(self._fetch_single_macro, category, file): file
                        for file in json_files
                    }
                    for future in as_completed(future_to_file):
                        result = future.result()
                        if result:
                            macros.append(result)
            
            # Sort macros by filename to maintain a consistent presentation
            macros.sort(key=lambda x: x.get('_metadata', {}).get('filename', '').lower())
            
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
        
        # Use fast parallelized get_all_macros
        macros = self.get_all_macros(sort_by='name')
        
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
    
    def get_all_macros(self, sort_by: str = 'name', force_refresh: bool = False) -> List[Dict]:
        """
        Get all macros from all categories in parallel.
        
        Args:
            sort_by: Sort method ('name', 'category', 'date')
            force_refresh: Cache bypass
        
        Returns:
            List of all macros
        """
        categories = self.get_categories(force_refresh=force_refresh)
        if not categories:
            return []
            
        all_macros = []
        
        # Parallelize fetching of macros across categories
        with ThreadPoolExecutor(max_workers=min(10, len(categories))) as executor:
            future_to_category = {
                executor.submit(self.get_macros_in_category, category, force_refresh): category
                for category in categories
            }
            for future in as_completed(future_to_category):
                try:
                    category_macros = future.result()
                    all_macros.extend(category_macros)
                except Exception as e:
                    logger.error(f"Error fetching macros in parallel for category: {e}")
        
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
*Submitted via Overcontrol*
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
        Uploads a macro via Webhook Gateway.
        Securely forwards data to a middleman (e.g. Make.com) which handles the GitHub commit.
        """
        submission_url = self.config.get('community', {}).get('submission_url')
        
        # Fallback to github section if not in community (backward compatibility if needed)
        if not submission_url:
             submission_url = self.config.get('github', {}).get('submission_url')

        if not submission_url:
            return {"status": "error", "message": "Submission URL not configured. Please check config.json"}

        try:
            logger.info(f"Submitting macro '{macro_data.get('name')}' to webhook...")
            
            # Validations
            if not macro_data.get('name'):
                 return {"status": "error", "message": "Invalid data: Missing name"}

            # details check based on type
            ctype = macro_data.get('type', 'macro')
            
            if ctype == 'profile':
                if not macro_data.get('profile'):
                    return {"status": "error", "message": "Invalid profile data"}
            else:
                # It's a macro
                # Check for valid content fields (actions, command, path, or legacy commands)
                base = macro_data.get('macro', macro_data)
                
                valid_keys = ['actions', 'command', 'path', 'commands']
                has_content = any(key in base for key in valid_keys)
                
                if not has_content:
                    logger.warning(f"Macro validation failed. Keys found: {list(base.keys())}")
                    return {"status": "error", "message": "Invalid macro data: Missing actions, command, or path"}

            # Send to Webhook
            response = self.session.post(submission_url, json=macro_data, timeout=15)
            
            if response.status_code in [200, 201]:
                logger.info("Submission successful via webhook")

                # --- CACHE INJECTION (Fix for "Restart Required") ---
                try:
                    # 1. Normalize category (GitHub folders are typically lowercase)
                    category_raw = macro_data.get('category', 'other')
                    category_key = category_raw.lower()
                    
                    # 2. Prime the cache! 
                    # CRITICAL: Call get_macros_in_category to populate the cache with existing items from GitHub.
                    # If we just created a new list [], we would hide all existing macros in this category.
                    # This call returns a reference to the list inside self._macros_cache
                    current_list = self.get_macros_in_category(category_key)
                    
                    # 3. Create mock entry
                    mock_entry = macro_data.copy()
                    
                    # Add metadata
                    if '_metadata' not in mock_entry:
                        mock_entry['_metadata'] = {
                            'category': category_raw, # Keep original casing for display if needed
                            'filename': f"{macro_data.get('name')}.json",
                            'download_url': None, 
                            'size': 0
                        }
                    
                    # Add timestamps
                    if 'uploaded_at' not in mock_entry:
                        import datetime
                        mock_entry['uploaded_at'] = datetime.datetime.now().isoformat()
                        
                    # 4. Inject
                    # Avoid duplicates if possible (simple name check)
                    exists = any(m.get('name') == mock_entry.get('name') for m in current_list)
                    if not exists:
                        current_list.insert(0, mock_entry)
                        logger.info(f"Injected '{macro_data.get('name')}' into local cache for '{category_key}'")
                    else:
                        logger.info(f"Macro '{macro_data.get('name')}' already in cache, skipping injection")
                    
                except Exception as e:
                    logger.warning(f"Failed to inject into cache: {e}")

                return {"status": "success", "message": "Macro submitted for review!"}
            else:
                logger.error(f"Webhook Error: {response.status_code} - {response.text}")
                return {"status": "error", "message": f"Server rejected submission (Code {response.status_code})"}

        except Exception as e:
            logger.error(f"Submission exception: {e}")
            return {"status": "error", "message": f"Connection failed: {str(e)}"}

    def clear_cache(self):
        """Clear the macro cache."""
        self._categories_cache = None
        self._macros_cache = {}
        logger.info("Cleared community library cache")
