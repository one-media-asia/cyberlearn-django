from django.db import models


class TrialUsage(models.Model):
    session_key = models.CharField(max_length=40, unique=True)
    supabase_user_id = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
    )
    prompts_used = models.PositiveSmallIntegerField(default=0)
    paid_access = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        identity = str(self.supabase_user_id) if self.supabase_user_id else self.session_key[:8]
        return f"{identity} — {self.prompts_used} prompts"
