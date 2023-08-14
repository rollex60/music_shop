import operator
from calendar import monthrange
from datetime import datetime

from django.conf import settings

from django.db import models
from django.urls import reverse
from django.db import connection
from django.db.models.signals import post_save, pre_save
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.utils import timezone
from django.utils.safestring import mark_safe

from utils import upload_function


class MediaType(models.Model):
    """Media carrier"""

    name = models.CharField(max_length=100, verbose_name='Media name')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Media carrier'
        verbose_name_plural = 'Media carriers'


class Member(models.Model):
    """Musician"""

    name = models.CharField(max_length=255, verbose_name='Musicians name')
    slug = models.SlugField()
    image = models.ImageField(upload_to=upload_function, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Musician'
        verbose_name_plural = 'Musicians'


class Genre(models.Model):
    """Musical genre"""

    name = models.CharField(max_length=50, verbose_name='Genre name')
    slug = models.SlugField()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Genre'
        verbose_name_plural = 'Genres'


class Artist(models.Model):
    """Artist"""

    name = models.CharField(max_length=255, verbose_name='Artist/group')
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE)
    members = models.ManyToManyField(Member, verbose_name='Members', related_name='artist')
    description = models.TextField(verbose_name='Band biography', default='Description coming later')
    image_gallery = GenericRelation('imagegallery')
    slug = models.SlugField()
    image = models.ImageField(upload_to=upload_function, null=True, blank=True)

    def __str__(self):
        return f"{self.name} | {self.genre.name}"

    def get_absolute_url(self):
        return reverse('artist_detail', kwargs={'artist_slug': self.slug})

    class Meta:
        verbose_name = 'Artist'
        verbose_name_plural = 'Artists'


class AlbumManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset()

    def get_month_bestseller(self):
        today = datetime.today()
        year, month = today.year, today.month
        first_day = datetime(year, month, 1)
        last_day = datetime(year, month, monthrange(year, month)[1])
        query = f"""
            SELECT shop_product.id as product_id, SUM(distinct shop_cart_product.qty) as total_qty
            FROM musicshop_order as shop_order
            JOIN musicshop_cart as shop_cart on shop_order.cart_id = shop_cart.id
            JOIN musicshop_cartproduct as shop_cart_product on shop_cart.id = shop_cart_product.cart_id
            JOIN musicshop_album as shop_product on shop_cart_product.object_id=shop_product.id
            WHERE shop_order.order_date >= '{first_day}' and shop_order.order_date <= '{last_day}'
            GROUP BY product_id
            ORDER BY total_qty DESC
            LIMIT 1
        """
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()
        if row:
            product_id, qty = row
            album = Album.objects.get(pk=product_id)
            return album, qty
        return None, None


class Album(models.Model):
    """Artist album"""

    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, verbose_name='Executor')
    name = models.CharField(max_length=255, verbose_name='Album name')
    media_type = models.ForeignKey(MediaType, verbose_name='Carrier', on_delete=models.CASCADE)
    songs_list = models.TextField(verbose_name='Tracklist')
    release_date = models.DateField(verbose_name='Date of release')
    slug = models.SlugField()
    description = models.TextField(verbose_name='Description', default='Description coming later')
    stock = models.IntegerField(default=1, verbose_name='Availability in stock')
    out_of_stock = models.BooleanField(default=False, verbose_name='Not available')
    image_gallery = GenericRelation('imagegallery')
    price = models.DecimalField(max_digits=9, decimal_places=2, verbose_name='Price')
    offer_of_the_week = models.BooleanField(default=False, verbose_name='Offer of the week?')
    image = models.ImageField(upload_to=upload_function)
    objects = AlbumManager()

    def __str__(self):
        return f"{self.id} | {self.artist.name} | {self.name}"

    @property
    def ct_model(self):
        return self._meta.model_name

    def get_absolute_url(self):
        return reverse('album_detail', kwargs={'artist_slug': self.artist.slug, 'album_slug': self.slug})

    class Meta:
        verbose_name = 'Album'
        verbose_name_plural = 'Albums'


class CartProduct(models.Model):
    """Cart product"""

    MODEL_CARTPRODUCT_DISPLAY_NAME_MAP = {
        "Album": {"is_constructable": True, "fields": ["name", "artist.name"], "separator": ' - '}
    }

    user = models.ForeignKey('Customer', verbose_name='Buyer', on_delete=models.CASCADE)
    cart = models.ForeignKey('Cart', verbose_name='Cart', on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    qty = models.PositiveIntegerField(default=1)
    final_price = models.DecimalField(max_digits=9, decimal_places=2, verbose_name='Total price')

    def __str__(self):
        return f"Product: {self.content_object.name} (for the cart)"

    @property
    def display_name(self):
        model_fields = self.MODEL_CARTPRODUCT_DISPLAY_NAME_MAP.get(self.content_object.__class__._meta.model_name.capitalize())
        if model_fields and model_fields['is_constructable']:
            display_name = model_fields['separator'].join(
                [operator.attrgetter(field)(self.content_object) for field in model_fields['fields']]
            )
            return display_name
        if model_fields and not model_fields['is_constructable']:
            display_name = operator.attrgetter(model_fields['field'])(self.content_object)
            return display_name

        return self.content_object

    def save(self, *args, **kwargs):
        self.final_price = self.qty * self.content_object.price
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Cart product'
        verbose_name_plural = 'Cart products'


class Cart(models.Model):
    """Cart"""

    owner = models.ForeignKey('Customer', verbose_name='Buyer', on_delete=models.CASCADE)
    products = models.ManyToManyField(
        CartProduct, blank=True, related_name='related_cart', verbose_name='Shopping cart products'
    )
    total_products = models.IntegerField(default=0, verbose_name='Total number of goods')
    final_price = models.DecimalField(max_digits=9, decimal_places=2, verbose_name='Total price', null=True, blank=True)
    in_order = models.BooleanField(default=False)
    for_anonymous_user = models.BooleanField(default=False)

    def __str__(self):
        return str(self.id)

    def products_in_cart(self):
        return [c.content_object for c in self.products.all()]

    class Meta:
        verbose_name = 'Cart'
        verbose_name_plural = 'Carts'


class Order(models.Model):
    """User order"""

    STATUS_NEW = 'new'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_READY = 'is_ready'
    STATUS_COMPLETED = 'completed'

    BUYING_TYPE_SELF = 'self'
    BUYING_TYPE_DELIVERY = 'delivery'

    STATUS_CHOICES = (
        (STATUS_NEW, 'New order'),
        (STATUS_IN_PROGRESS, 'Order in processing'),
        (STATUS_READY, 'Order is ready'),
        (STATUS_COMPLETED, 'Order received by customer')
    )

    BUYING_TYPE_CHOICES = (
        (BUYING_TYPE_SELF, 'Pickup'),
        (BUYING_TYPE_DELIVERY, 'Delivery')
    )

    customer = models.ForeignKey('Customer', verbose_name='Buyer', related_name='orders', on_delete=models.CASCADE)
    first_name = models.CharField(max_length=255, verbose_name='Name')
    last_name = models.CharField(max_length=255, verbose_name='Surname')
    phone = models.CharField(max_length=20, verbose_name='Telephone')
    cart = models.ForeignKey(Cart, verbose_name='Cart', null=True, blank=True, on_delete=models.CASCADE)
    address = models.CharField(max_length=1024, verbose_name='Address', null=True, blank=True)
    status = models.CharField(max_length=100, verbose_name='Order status', choices=STATUS_CHOICES, default=STATUS_NEW)
    buying_type = models.CharField(max_length=100, verbose_name='Order type', choices=BUYING_TYPE_CHOICES)
    comment = models.TextField(verbose_name='Comment to the order', null=True, blank=True)
    created_at = models.DateField(verbose_name='Order creation date', auto_now=True)
    order_date = models.DateField(verbose_name='Date of receipt of the order', default=timezone.now)

    def __str__(self):
        return str(self.id)

    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'


class Customer(models.Model):
    """Buyer"""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name='Buyer', on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True, verbose_name='Active?')
    customer_orders = models.ManyToManyField(
        Order, blank=True, verbose_name='Buyer orders',related_name='related_customer'
    )
    wishlist = models.ManyToManyField(Album, blank=True, verbose_name='List of expected')
    phone = models.CharField(max_length=20, verbose_name='Phone number')
    address = models.TextField(null=True, blank=True, verbose_name='Address')

    def __str__(self):
        return f"{self.user.username}"

    class Meta:
        verbose_name = 'Buyer'
        verbose_name_plural = 'Buyers'


class NotificationManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset()

    def all(self, recipient):
        return self.get_queryset().filter(
            recipient=recipient,
            read=False
        )

    def make_all_read(self, recipient):
        qs = self.get_queryset().filter(recipient=recipient, read=False)
        qs.update(read=True)


class Notification(models.Model):
    """Notifications"""

    recipient = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name='Recipient')
    text = models.TextField()
    read = models.BooleanField(default=False)
    objects = NotificationManager()

    def __str__(self):
        return f"Notice for {self.recipient.user.username} | id={self.id}"

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'


class ImageGallery(models.Model):
    """Image Gallery"""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    image = models.ImageField(upload_to=upload_function)
    use_in_slider = models.BooleanField(default=False)

    def __str__(self):
        return f"Image for {self.content_object}"

    def image_url(self):
        return mark_safe(f'<img src="{self.image.url}" width="auto" height="200px"')

    class Meta:
        verbose_name = 'Image gallery'
        verbose_name_plural = verbose_name


def check_previous_qty(instance, **kwargs):
    try:
        album = Album.objects.get(id=instance.id)
    except Album.DoesNotExist:
        return None
    instance.out_of_stock = True if not album.stock else False


def send_notification(instance, **kwargs):
    if instance.stock and instance.out_of_stock:
        customers = Customer.objects.filter(
            wishlist__in=[instance]
        )
        if customers.count():
            for c in customers:
                Notification.objects.create(
                    recipient=c,
                    text=mark_safe(f'Position <a href="{instance.get_absolute_url()}">{instance.name}</a>, '
                                   f'what you expect is in stock.')
                )
                c.wishlist.remove(instance)


post_save.connect(send_notification, sender=Album)
pre_save.connect(check_previous_qty, sender=Album)