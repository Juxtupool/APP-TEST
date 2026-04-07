from app.core import safe_api, ApiResponse
from pathlib import Path

class IconMixin:
    @safe_api
    def get_icon_categories(self):
        """Get list of icon categories (subdirectories)."""
        # We assume APP_ROOT is defined in the main Api class or passed
        # For mixins, we will rely on self._get_app_root() or similar
        icons_dir = self._app_root / "app" / "assets" / "icons"
        if not icons_dir.exists():
            return ApiResponse.success(data=[], message="No categories found")
        
        categories = [d.name for d in icons_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        return ApiResponse.success(sorted(categories), "Categories found")

    @safe_api
    def get_icons(self, category):
        """Get icons in a category."""
        icons_dir = self._app_root / "app" / "assets" / "icons" / category
        if not icons_dir.exists():
            return ApiResponse.error("Category not found")
        
        valid_exts = {'.png', '.svg', '.jpg', '.jpeg', '.gif'}
        icons = []
        for f in icons_dir.iterdir():
            if f.is_file() and f.suffix.lower() in valid_exts:
                icons.append(f"icons/{category}/{f.name}")
        
        return ApiResponse.success(sorted(icons))

    def _ensure_icon_cache(self):
        """Load icons from disk into memory if not already loaded."""
        if self._icon_cache is not None:
            return

        try:
            icons_dir = self._app_root / "app" / "assets" / "icons"
            if not icons_dir.exists():
                self._icon_cache = {}
                return
            
            data = {}
            valid_exts = {'.png', '.svg', '.jpg', '.jpeg', '.gif'}
            categories = sorted([d for d in icons_dir.iterdir() if d.is_dir() and not d.name.startswith('.')])
            
            for category_dir in categories:
                cat_name = category_dir.name
                icons = []
                for f in category_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in valid_exts:
                        icons.append(f"icons/{cat_name}/{f.name}")
                if icons:
                    data[cat_name] = sorted(icons)
            
            self._icon_cache = data
            self.logger.info("Icon cache built successfully")
        except Exception as e:
            self.logger.error(f"Error building icon cache: {e}")
            self._icon_cache = {}

    @safe_api
    def get_all_icons_grouped(self):
        """Get all icons grouped by category (Cached)."""
        self._ensure_icon_cache()
        return ApiResponse.success(self._icon_cache)

    @safe_api
    def search_icons(self, query):
        """Search for icons across all categories (Cached)."""
        self._ensure_icon_cache()
        query = query.lower()
        matches = []
        
        for category, icons in self._icon_cache.items():
            for icon_path in icons:
                filename = icon_path.split('/')[-1].lower()
                if query in filename:
                    matches.append(icon_path)
        
        return ApiResponse.success(sorted(matches))
