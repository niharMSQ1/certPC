from django.db import models

class Framework(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return self.name

class Policy(models.Model):
    framework = models.ForeignKey(Framework, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.title} ({self.framework.name})"

class PolicyVersion(models.Model):
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE)
    version = models.CharField(max_length=50)
    uploaded_file = models.FileField(upload_to='policies/')
    created_at = models.DateTimeField(auto_now_add=True)
    change_summary = models.JSONField(default=dict) 

    def __str__(self):
        return f"{self.policy.title} - {self.version}"

class PolicySection(models.Model):
    version = models.ForeignKey(PolicyVersion, on_delete=models.CASCADE, related_name='sections')
    section_number = models.CharField(max_length=50)
    content = models.TextField()
    archived = models.BooleanField(default=False)

    class Meta:
        unique_together = ('version', 'section_number')

    def __str__(self):
        return f"{self.version.policy.title} [{self.section_number}]"

class PolicyDiff(models.Model):
    version = models.ForeignKey(PolicyVersion, on_delete=models.CASCADE, related_name='diffs')
    section_number = models.CharField(max_length=50)
    diff_text = models.TextField()
    change_details = models.JSONField(default=dict)
    
    def __str__(self):
        return f"{self.version.policy.title} [{self.section_number}] changes"