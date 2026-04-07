import logging
from typing import Dict

logger = logging.getLogger(__name__)

class CommunityMixin:
    def get_community_categories(self):
        """Get list of community macro categories."""
        try:
            categories = self._community_library_service.get_categories()
            return {"status": "success", "categories": categories}
        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_community_macros(self, category: str = None, search: str = None, force_refresh: bool = False):
        """Get community macros by category or search query."""
        try:
            if search:
                macros = self._community_library_service.search_macros(search)
            elif category:
                macros = self._community_library_service.get_macros_in_category(category, force_refresh=force_refresh)
            else:
                macros = self._community_library_service.get_all_macros(force_refresh=force_refresh)
            
            return {"status": "success", "macros": macros}
        except Exception as e:
            logger.error(f"Error fetching macros: {e}")
            return {"status": "error", "message": str(e)}
    
    def install_community_macro(self, macro_data: Dict):
        """Install a community macro OR profile."""
        try:
            install_type = macro_data.get('type', 'macro')
            
            if install_type == 'profile':
                profile_content = macro_data.get('profile', {})
                if not profile_content:
                    return {"status": "error", "message": "Invalid profile data"}
                
                profile_content['origin'] = 'community-profile'
                
                base_name = macro_data.get('name', 'Community Profile')
                profile_name = base_name
                counter = 1
                
                while profile_name in self._profiles.get("profiles", {}):
                    profile_name = f"{base_name} ({counter})"
                    counter += 1
                
                self._profiles["profiles"][profile_name] = profile_content
                self._profiles["active_profile"] = profile_name 
                self._current_profile_name = profile_name
                
                self._profile_service.save_profiles(self._profiles)
                self._profile_switcher.notify_manual_switch(profile_name) 
                
                logger.info(f"Installed community profile: {profile_name}")
                return {"status": "success", "name": profile_name, "type": "profile"}

            else:
                macro_content = macro_data.get('macro', macro_data)
                macro_content['origin'] = 'community'
                
                profile_data = self._profiles.get("profiles", {}).get(self._current_profile_name, {})
                if 'macros' not in profile_data:
                    profile_data['macros'] = {}
                
                macro_name = macro_data.get('name', 'Unnamed Macro')
                base_name = macro_name
                counter = 1
                
                while macro_name in profile_data['macros']:
                    macro_name = f"{base_name} ({counter})"
                    counter += 1
                
                profile_data['macros'][macro_name] = macro_content
                self._profiles["profiles"][self._current_profile_name] = profile_data
                self._profile_service.save_profiles(self._profiles)
                
                logger.info(f"Installed community macro: {macro_name}")
                return {"status": "success", "name": macro_name, "type": "macro"}

        except Exception as e:
            logger.error(f"Error installing item: {e}")
            return {"status": "error", "message": str(e)}
    
    def submit_community_macro(self, macro_data: Dict):
        """Submit a macro directly to the GitHub community repo."""
        try:
            result = self._community_library_service.upload_macro(macro_data)
            return result
        except Exception as e:
            logger.error(f"Error submitting macro: {e}")
            return {"status": "error", "message": str(e)}
