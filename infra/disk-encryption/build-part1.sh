#!/bin/bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

WORK_DIR="/work/luks-build"
BASE_IMAGE_URL="https://downloads.raspberrypi.org/raspios_lite_arm64_latest"
SOURCE_IMAGE="$WORK_DIR/source.img"
TARGET_IMAGE="$WORK_DIR/target.img"
TARGET_SIZE_MB=4096

echo "=== [0/8] Nettoyage prealable complet ==="
apt-get update -qq
apt-get install -y -qq dmsetup 2>/dev/null || true

# Demonte TOUS les points de montage possibles d'une tentative precedente,
# dans l'ordre inverse de leur creation (le plus profond d'abord).
umount "$WORK_DIR/tgt_root/dev" 2>/dev/null || true
umount "$WORK_DIR/tgt_root/proc" 2>/dev/null || true
umount "$WORK_DIR/tgt_root/sys" 2>/dev/null || true
umount "$WORK_DIR/tgt_boot" 2>/dev/null || true
umount "$WORK_DIR/tgt_root" 2>/dev/null || true
umount "$WORK_DIR/src_boot" 2>/dev/null || true
umount "$WORK_DIR/src_root" 2>/dev/null || true

cryptsetup luksClose cryptroot 2>/dev/null || true
dmsetup remove -f cryptroot 2>/dev/null || true
for d in $(dmsetup ls 2>/dev/null | awk '{print $1}'); do
    dmsetup remove -f "$d" 2>/dev/null || true
done
for i in $(seq 0 15); do
    losetup -d "/dev/loop$i" 2>/dev/null || true
done
echo "Nettoyage termine."

echo "=== [1/8] Dependances systeme ==="
apt-get install -y -qq \
    wget xz-utils parted kpartx cryptsetup cryptsetup-initramfs \
    rsync curl ca-certificates dosfstools e2fsprogs qemu-user-static

mkdir -p "$WORK_DIR"

echo "=== [2/8] Telechargement de l'image source ==="
if [ ! -f "$SOURCE_IMAGE" ]; then
    if [ ! -f "$WORK_DIR/base.img.xz" ]; then
        wget -q --show-progress -O "$WORK_DIR/base.img.xz" "$BASE_IMAGE_URL"
    fi
    xz -dk -T0 -c "$WORK_DIR/base.img.xz" > "$SOURCE_IMAGE"
fi

echo "=== [3/8] Montage de la source ==="
SRC_LOOP=$(losetup -f --show "$SOURCE_IMAGE")
kpartx -av "$SRC_LOOP"
sleep 1
SRC_BOOT_DEV="/dev/mapper/$(basename ${SRC_LOOP})p1"
SRC_ROOT_DEV="/dev/mapper/$(basename ${SRC_LOOP})p2"
mkdir -p "$WORK_DIR/src_boot" "$WORK_DIR/src_root"
mount "$SRC_BOOT_DEV" "$WORK_DIR/src_boot" -o ro
mount "$SRC_ROOT_DEV" "$WORK_DIR/src_root" -o ro

echo "=== [4/8] Creation de l'image cible chiffree ==="
dd if=/dev/zero of="$TARGET_IMAGE" bs=1M count="$TARGET_SIZE_MB" status=progress

TGT_LOOP=$(losetup -f --show "$TARGET_IMAGE")
parted -s "$TGT_LOOP" mklabel msdos
parted -s "$TGT_LOOP" mkpart primary fat32 1MiB 257MiB
parted -s "$TGT_LOOP" mkpart primary 257MiB 100%
partprobe "$TGT_LOOP" || true
kpartx -av "$TGT_LOOP"
sleep 1

TGT_BOOT="/dev/mapper/$(basename ${TGT_LOOP})p1"
TGT_ROOT_RAW="/dev/mapper/$(basename ${TGT_LOOP})p2"

mkfs.vfat -F 32 "$TGT_BOOT"

echo "=== [5/8] Chiffrement LUKS2 ==="
LUKS_RECOVERY_PASSWORD=$(openssl rand -base64 24)
echo "$LUKS_RECOVERY_PASSWORD" > "$WORK_DIR/RECOVERY_PASSWORD.txt"
chmod 600 "$WORK_DIR/RECOVERY_PASSWORD.txt"

echo -n "$LUKS_RECOVERY_PASSWORD" | cryptsetup luksFormat --type luks2 --batch-mode "$TGT_ROOT_RAW" -
echo -n "$LUKS_RECOVERY_PASSWORD" | cryptsetup luksOpen "$TGT_ROOT_RAW" cryptroot -
mkfs.ext4 -q /dev/mapper/cryptroot

echo "=== [6/8] Copie des donnees ==="
mkdir -p "$WORK_DIR/tgt_boot" "$WORK_DIR/tgt_root"
mount "$TGT_BOOT" "$WORK_DIR/tgt_boot"
mount /dev/mapper/cryptroot "$WORK_DIR/tgt_root"

rsync -aHAX --info=progress2 "$WORK_DIR/src_root/" "$WORK_DIR/tgt_root/"
rsync -aHAX --info=progress2 "$WORK_DIR/src_boot/" "$WORK_DIR/tgt_boot/"

echo "=== [7/8] Installation de Clevis (qemu explicite, sans binfmt_misc) ==="
cp /usr/bin/qemu-aarch64-static "$WORK_DIR/tgt_root/usr/bin/"
mount --bind /dev "$WORK_DIR/tgt_root/dev"
mount --bind /proc "$WORK_DIR/tgt_root/proc"
mount --bind /sys "$WORK_DIR/tgt_root/sys"

chroot "$WORK_DIR/tgt_root" /usr/bin/qemu-aarch64-static /usr/bin/apt-get update -qq
chroot "$WORK_DIR/tgt_root" /usr/bin/qemu-aarch64-static /usr/bin/env DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get install -y -qq \
    cryptsetup cryptsetup-initramfs clevis clevis-luks clevis-initramfs

umount "$WORK_DIR/tgt_root/sys" "$WORK_DIR/tgt_root/proc" "$WORK_DIR/tgt_root/dev"

echo "=== [8/8] Sauvegarde des variables ==="
cat > "$WORK_DIR/vars.env" <<EOF
SRC_LOOP=$SRC_LOOP
TGT_LOOP=$TGT_LOOP
TGT_BOOT=$TGT_BOOT
TGT_ROOT_RAW=$TGT_ROOT_RAW
LUKS_RECOVERY_PASSWORD=$LUKS_RECOVERY_PASSWORD
EOF

echo "=== PARTIE 1 TERMINEE ==="
