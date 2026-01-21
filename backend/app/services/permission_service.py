from typing import List, Optional
from app.models.account import Account

class PermissionService:
    @staticmethod
    def check_permission(account: Account, action: str) -> bool:
        """
        Check if account has permission to perform action based on tier.
        
        Tiers:
        - tier1 (Premium): Main support/official accounts. NO mass actions.
        - tier2 (Support): Trusted shill/support accounts. Limited mass actions.
        - tier3 (Disposable): Worker accounts. All mass actions allowed.
        """
        tier = account.tier or "tier3"
        
        # Define restricted actions for high tiers
        # Actions: mass_dm, invite, shill, scrape
        
        if tier == "tier1":
            # Premium accounts should NOT do risky things
            if action in ["mass_dm", "invite", "scrape"]:
                return False
            return True
            
        elif tier == "tier2":
            # Support accounts can do some things but carefully
            if action == "mass_dm":
                return False # Avoid mass DM for support accounts too
            return True
            
        else: # tier3
            # Disposable accounts can do anything
            return True

    @staticmethod
    def filter_accounts_for_action(accounts: List[Account], action: str) -> List[Account]:
        """
        Return only accounts that are allowed to perform the action
        """
        return [acc for acc in accounts if PermissionService.check_permission(acc, action)]
