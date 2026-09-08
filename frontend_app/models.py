from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User


# ---------------------------------------------------------------------------
# Choices
# ---------------------------------------------------------------------------

ROCK_TYPE_CHOICES = [
    ('granite', 'Granite'),
    ('sandstone', 'Sandstone'),
    ('limestone', 'Limestone'),
    ('boulder', 'Boulder'),
    ('indoor', 'Indoor'),
]

# French-style grading (the project uses 4A-8B). Order matters for filtering.
GRADE_CHOICES = [
    ('4A', '4A'), ('4B', '4B'), ('4C', '4C'),
    ('5A', '5A'), ('5B', '5B'), ('5C', '5C'),
    ('6A', '6A'), ('6B', '6B'), ('6C', '6C'),
    ('7A', '7A'), ('7B', '7B'), ('7C', '7C'),
    ('8A', '8A'), ('8B', '8B'),
]

ROUTE_TYPE_CHOICES = [
    ('sport', 'Sport'),
    ('trad', 'Trad'),
    ('boulder', 'Boulder'),
    ('toprope', 'Top Rope'),
]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Crag(models.Model):
    """A climbing area / crag."""

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    lat = models.DecimalField(max_digits=9, decimal_places=6, default=1.3521)
    lng = models.DecimalField(max_digits=9, decimal_places=6, default=103.8198)
    rock_type = models.CharField(
        max_length=20, choices=ROCK_TYPE_CHOICES, default='granite'
    )
    difficulty_min = models.CharField(
        max_length=3, choices=GRADE_CHOICES, default='4A'
    )
    difficulty_max = models.CharField(
        max_length=3, choices=GRADE_CHOICES, default='6B'
    )
    length_m = models.IntegerField(default=15)
    hazards = models.TextField(blank=True, help_text='Safety notes for the crag')
    image = models.URLField(blank=True, help_text='Optional hero image URL')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            n = 2
            while Crag.objects.filter(slug=slug).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def grade_order(self):
        """Index of difficulty_min within GRADE_CHOICES, for numeric filtering."""
        return dict((g, i) for i, (g, _) in enumerate(GRADE_CHOICES)).get(
            self.difficulty_min, 0
        )


class Route(models.Model):
    """A single climb within a crag."""

    crag = models.ForeignKey(Crag, related_name='routes', on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    grade = models.CharField(max_length=3, choices=GRADE_CHOICES, default='5A')
    route_type = models.CharField(
        max_length=10, choices=ROUTE_TYPE_CHOICES, default='sport'
    )
    length_m = models.IntegerField(default=15)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['grade', 'name']

    def __str__(self):
        return f'{self.crag.name} – {self.name} ({self.grade})'


class Favorite(models.Model):
    """A user's saved crag."""

    user = models.ForeignKey(User, related_name='favorites', on_delete=models.CASCADE)
    crag = models.ForeignKey(Crag, related_name='favorited_by', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'crag')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} ❤ {self.crag.name}'


# ---------------------------------------------------------------------------
# Community Forum
# ---------------------------------------------------------------------------

class ForumPost(models.Model):
    """A community discussion post."""

    author = models.ForeignKey(User, related_name='forum_posts', on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    content = models.TextField()
    crag = models.ForeignKey(
        Crag, related_name='forum_posts', on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.author.username}: {self.title[:40]}'


class ForumComment(models.Model):
    """A reply to a forum post."""

    post = models.ForeignKey(ForumPost, related_name='comments', on_delete=models.CASCADE)
    author = models.ForeignKey(User, related_name='forum_comments', on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.author.username} on #{self.post_id}'


class ForumLike(models.Model):
    """A like on a forum post (one per user)."""

    user = models.ForeignKey(User, related_name='forum_likes', on_delete=models.CASCADE)
    post = models.ForeignKey(ForumPost, related_name='likes', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')

    def __str__(self):
        return f'{self.user.username} likes #{self.post_id}'
