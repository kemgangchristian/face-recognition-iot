#!/bin/bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

WORK_DIR="/work/luks-build"
TANG_HOSTNAME="tang-server"
TANG_PORT="7500"
MAC_LAN_IP="${1:?Usage: $0 <IP_LAN_reelle_de_ton_Mac>}"
OUTPUT_IMAGE="/work/face-recognition-pi-encrypted.img"

if [ ! -f "$WORK_DIR/vars.env" ]; then echo "ERREUR: vars.env absent"; exit 1; fi
source "$WORK_DIR/vars.env"
mountpoint -q "$WORK_DIR/tgt_root" || { echo "ERREUR: tgt_root non monte"; exit 1; }
cryptsetup status cryptroot >/dev/null 2>&1 || { echo "ERREUR: cryptroot ferme"; exit 1; }

echo "=== [9/11] Preparation Clevis/Tang ==="

curl -sf --max-time 5 "http://${MAC_LAN_IP}:${TANG_PORT}/adv" >/dev/null || { echo "ERREUR: Tang injoignable"; exit 1; }
echo "OK: Tang joignable"
sed -i "/$TANG_HOSTNAME/d" "$WORK_DIR/tgt_root/etc/hosts"
echo "$MAC_LAN_IP $TANG_HOSTNAME" >> "$WORK_DIR/tgt_root/etc/hosts"

mount --bind /dev "$WORK_DIR/tgt_root/dev"
mount --bind /proc "$WORK_DIR/tgt_root/proc"
mount --bind /sys "$WORK_DIR/tgt_root/sys"

echo -n "$LUKS_RECOVERY_PASSWORD" | chroot "$WORK_DIR/tgt_root" /usr/bin/qemu-aarch64-static /bin/bash /usr/bin/clevis luks bind -f -y -k - -d "$TGT_ROOT_RAW" tang "{\"url\":\"http://${MAC_LAN_IP}:${TANG_PORT}\"}"

umount "$WORK_DIR/tgt_root/sys" "$WORK_DIR/tgt_root/proc" "$WORK_DIR/tgt_root/dev"

echo "OK: binding Clevis effectue"

echo "=== [10/11] Configuration du demarrage chiffre ==="
CRYPT_UUID=$(blkid -s UUID -o value "$TGT_ROOT_RAW")
echo "UUID cryptroot: $CRYPT_UUID"

CMDLINE="$WORK_DIR/tgt_boot/cmdline.txt"
echo "Avant: $(cat $CMDLINE)"
sed -i "s|root=PARTUUID=[^ ]*|root=/dev/mapper/cryptroot|" "$CMDLINE"
sed -i "s| cryptdevice=[^ ]*||g" "$CMDLINE"
grep -q "rootdelay=" "$CMDLINE" || sed -i "s|rootwait|rootwait rootdelay=10|" "$CMDLINE"
echo "Apres: $(cat $CMDLINE)"

cat > "$WORK_DIR/tgt_root/etc/crypttab" <<EOF
cryptroot UUID=${CRYPT_UUID} none luks,discard
EOF

# Reconstruction complete de fstab plutot qu'un patch sed fragile -- le
# fstab original a un espacement variable (espaces/tabs d'alignement) qui
# fait echouer silencieusement un sed base sur un motif exact.
NEW_BOOT_PARTUUID=$(blkid -s PARTUUID -o value "$TGT_BOOT")
echo "Nouveau PARTUUID boot: ${NEW_BOOT_PARTUUID}"

cat > "$WORK_DIR/tgt_root/etc/fstab" <<EOF
proc            /proc           proc    defaults          0       0
PARTUUID=${NEW_BOOT_PARTUUID}  /boot/firmware  vfat    defaults          0       2
/dev/mapper/cryptroot  /               ext4    defaults,noatime  0       1
EOF

echo "Contenu fstab final :"
cat "$WORK_DIR/tgt_root/etc/fstab"

echo "--- Creation du hook clevis-network ---"
cat > "$WORK_DIR/tgt_root/etc/initramfs-tools/hooks/clevis-network" <<'HOOK_EOF'
#!/bin/sh
PREREQ=""
prereqs() { echo "$PREREQ"; }
case $1 in prereqs) prereqs; exit 0;; esac
. /usr/share/initramfs-tools/hook-functions
copy_exec /bin/busybox || true
copy_exec /usr/bin/busybox || true
copy_exec /bin/ip || true
copy_exec /usr/bin/ip || true
copy_exec /sbin/ip || true
copy_exec /usr/sbin/ip || true
copy_exec /usr/bin/curl || true
copy_exec /usr/bin/jose || true
copy_exec /usr/bin/jq || true
mkdir -p "${DESTDIR}/etc"
[ -f /etc/resolv.conf ] && cp /etc/resolv.conf "${DESTDIR}/etc/resolv.conf" 2>/dev/null || true
exit 0
HOOK_EOF
chmod 755 "$WORK_DIR/tgt_root/etc/initramfs-tools/hooks/clevis-network"

echo "--- Creation du script 00-clevis-wait-network ---"
mkdir -p "$WORK_DIR/tgt_root/etc/initramfs-tools/scripts/local-top"
cat > "$WORK_DIR/tgt_root/etc/initramfs-tools/scripts/local-top/00-clevis-wait-network" <<WAIT_EOF
#!/bin/sh
PREREQ=""
prereqs() { echo "\$PREREQ"; }
case \$1 in prereqs) prereqs; exit 0;; esac
. /scripts/functions
log_begin_msg "clevis-wait-network: demarrage"
IFACE="eth0"
STATIC_IP="192.168.1.200"
GATEWAY="192.168.1.254"
TANG_URL="http://${MAC_LAN_IP}:${TANG_PORT}/adv"
for mod in bcmgenet smsc95xx lan78xx dwc2; do modprobe "\$mod" 2>/dev/null || true; done
i=0
while [ ! -e "/sys/class/net/\$IFACE" ] && [ \$i -lt 30 ]; do sleep 1; i=\$((i+1)); done
[ -e "/sys/class/net/\$IFACE" ] || { log_failure_msg "iface absente"; exit 0; }
ip link set "\$IFACE" up 2>/dev/null || true
i=0
while [ \$i -lt 30 ]; do
    [ "\$(cat /sys/class/net/\$IFACE/carrier 2>/dev/null)" = "1" ] && break
    sleep 1; i=\$((i+1))
done
ip addr flush dev "\$IFACE" 2>/dev/null || true
ip addr add "\${STATIC_IP}/24" dev "\$IFACE" 2>/dev/null || true
ip route add default via "\$GATEWAY" dev "\$IFACE" 2>/dev/null || true
echo "nameserver \$GATEWAY" > /etc/resolv.conf 2>/dev/null || true
i=0
while [ \$i -lt 20 ]; do
    busybox wget -q -O - -T 3 "\$TANG_URL" >/dev/null 2>&1 && { log_success_msg "TANG OK"; log_end_msg; exit 0; }
    sleep 2; i=\$((i+2))
done
log_failure_msg "TANG INJOIGNABLE"
log_end_msg
exit 0
WAIT_EOF
chmod 755 "$WORK_DIR/tgt_root/etc/initramfs-tools/scripts/local-top/00-clevis-wait-network"

echo "--- Regeneration de l'initramfs ---"
mount --bind /dev "$WORK_DIR/tgt_root/dev"
mount --bind /proc "$WORK_DIR/tgt_root/proc"
mount --bind /sys "$WORK_DIR/tgt_root/sys"

chroot "$WORK_DIR/tgt_root" /usr/bin/qemu-aarch64-static /bin/bash /usr/sbin/update-initramfs -u -k all

umount "$WORK_DIR/tgt_root/sys" "$WORK_DIR/tgt_root/proc" "$WORK_DIR/tgt_root/dev"

echo "--- Copie des initramfs vers la FAT32 ---"
for k in "$WORK_DIR/tgt_root"/boot/initrd.img-*; do
    [ -e "$k" ] || continue
    kname=$(basename "$k")
    case "$kname" in
        *2712*) cp -v "$k" "$WORK_DIR/tgt_boot/initramfs_2712" ;;
        *v8*)   cp -v "$k" "$WORK_DIR/tgt_boot/initramfs8" ;;
        *)      cp -v "$k" "$WORK_DIR/tgt_boot/initramfs8" ;;
    esac
done
sync

echo "--- Configuration headless (userconf + ssh + hostname) ---"
echo 'admin:$6$8YqJaAWOVMQ61Ord$veggFhHmblb8PpSYryXFC5KTNXRbxehPYp1dapy2iynlP6cji4GTXVxjVLU.kLMzq8ezEo9fnVAm4IpIZY7Fm1' > "$WORK_DIR/tgt_boot/userconf.txt"
touch "$WORK_DIR/tgt_boot/ssh"
# Definit le hostname a la fois sur la partition boot (lu au premier boot)
# et directement dans le systeme de fichiers root, pour etre sur qu'il
# s'applique meme si le mecanisme boot/hostname.txt n'est pas repris par
# cette version de Raspberry Pi OS.
echo "face-recognition-pi" > "$WORK_DIR/tgt_boot/hostname.txt" 2>/dev/null || true
echo "face-recognition-pi" > "$WORK_DIR/tgt_root/etc/hostname"
sed -i "s|127.0.1.1.*|127.0.1.1\tface-recognition-pi|" "$WORK_DIR/tgt_root/etc/hosts"

echo "OK: userconf.txt, ssh et hostname configures"

echo "=== [11/11] Demontage et finalisation ==="
sync
umount "$WORK_DIR/tgt_boot" 2>/dev/null || true
umount "$WORK_DIR/tgt_root" 2>/dev/null || true
sleep 2
sync
cryptsetup luksClose cryptroot || {
    echo "Tentative de fermeture forcee..."
    dmsetup remove -f cryptroot
}
umount "$WORK_DIR/src_boot" 2>/dev/null || true
umount "$WORK_DIR/src_root" 2>/dev/null || true
for d in $(dmsetup ls 2>/dev/null | awk '/^loop/{print $1}'); do dmsetup remove -f "$d" 2>/dev/null || true; done
for i in $(seq 0 15); do losetup -d "/dev/loop$i" 2>/dev/null || true; done

cp -v "$WORK_DIR/target.img" "$OUTPUT_IMAGE"
sync

echo "=== TERMINE AVEC SUCCES ==="
echo "Image : $OUTPUT_IMAGE"
echo "MDP   : $WORK_DIR/RECOVERY_PASSWORD.txt"
