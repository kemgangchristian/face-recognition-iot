# Chiffrement disque complet (LUKS2 + NBDE/Tang-Clevis)

Prépare une image Raspberry Pi OS avec :
- Chiffrement LUKS2 de la partition root
- Déverrouillage automatique au démarrage via Tang (NBDE), sans mot de passe humain
- Configuration réseau statique dans l'initramfs (le DHCP n'étant pas fiable à ce stade)
- Configuration headless (utilisateur, SSH, hostname pré-configurés)

## Prérequis

- Docker Desktop sur Mac, avec accès `--privileged` fonctionnel
- Un serveur Tang accessible sur le réseau local (voir section ci-dessous)
- `qemu-user-static` fonctionne via invocation explicite (binfmt_misc peut être
  cassé sur certaines installations Docker Desktop — voir notes ci-dessous)

## Lancer le serveur Tang

Le serveur Tang doit tourner **avant** de lancer `build-part2.sh` (qui a besoin
de le contacter pour lier Clevis), et doit continuer à tourner en permanence
par la suite — c'est lui qui fournit la clé de déchiffrement à chaque
démarrage du Pi.

```bash
docker run -d \
  --name tang-server \
  --restart unless-stopped \
  -p 7500:8080 \
  -v tang-keys:/db \
  padhihomelab/tang
```

`--restart unless-stopped` : le serveur redémarre automatiquement avec ton Mac
— si Tang est injoignable au démarrage du Pi, celui-ci reste bloqué en attente
(comportement de sécurité voulu, voir section AIPD du projet).

**Vérifier que le serveur fonctionne :**

```bash
curl http://localhost:7500/adv
```

Doit retourner un JSON contenant les clés du serveur (payload/protected/signature).

**Récupérer l'empreinte du serveur** (utile pour vérification manuelle,
normalement auto-acceptée par le flag `-y` dans `build-part2.sh`) :

```bash
curl -s http://localhost:7500/adv > /tmp/adv.jws
docker cp /tmp/adv.jws tang-server:/tmp/adv.jws
docker exec tang-server sh -c "jose fmt -j /tmp/adv.jws -g payload -u - | jose b64 dec -i- | jose jwk thp -i-"
```

**Point d'attention** : le volume `tang-keys` contient les clés cryptographiques
du serveur — si ce volume est supprimé ou recréé, **toutes les images Pi déjà
liées à cette instance de Tang deviennent indéchiffrables** (le mot de passe
de récupération `RECOVERY_PASSWORD.txt` devient alors le seul accès). Ne
jamais faire `docker volume rm tang-keys` sans être certain.

## Récupérer l'IP LAN de ton Mac (pour le serveur Tang)

C'est cette IP que `build-part2.sh` prend en paramètre — elle doit être stable
(vérifier une réservation DHCP sur ta box si possible, sinon la clé cassera
au prochain changement d'IP) :

```bash
ipconfig getifaddr en0
```

## Générer le mot de passe de connexion (hash pour userconf.txt)

```bash
openssl passwd -6
```

Tape le mot de passe souhaité pour l'utilisateur `admin` — la commande retourne
un hash du type `$6$xxxxx$yyyyy...`. Colle ce hash (entre guillemets simples,
voir section "Difficultés" plus bas) dans `build-part2.sh`, par defaut "admin" comme password, ligne :

```bash
echo 'admin:$6$xxxxx$yyyyy...' > "$WORK_DIR/tgt_boot/userconf.txt"
```

**Le mot de passe en clair (pas le hash) sert ensuite à te connecter :**

```bash
ssh admin@face-recognition-pi.local
```

Si `.local` ne résout pas, trouve l'IP attribuée par ton routeur (page
d'administration de la box, ou `arp -a` depuis ton Mac après quelques
minutes de démarrage du Pi).

## Utilisation

```bash
mkdir -p ~/luks-pi-build && cd ~/luks-pi-build
cp /chemin/vers/infra/disk-encryption/build-part*.sh .

docker run -dit --privileged \
  -v $(pwd):/work \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e HOST_WORK_DIR="$(pwd)/luks-build" \
  --name luks-builder \
  debian:bookworm bash

docker exec -it luks-builder bash /work/build-part1.sh
docker exec -it luks-builder bash /work/build-part2.sh <IP_LAN_du_serveur_Tang>
```

Avant de lancer `build-part2.sh`, personnalise dans le script :
- `admin:$6$...` (ligne `userconf.txt`) : hash généré via `openssl passwd -6`
- `face-recognition-pi` : hostname souhaité
- `192.168.1.10` / `192.168.1.1` : IP statique et passerelle du Pi (script réseau initramfs)

## Résultat

Image prête à flasher : `face-recognition-pi-encrypted.img`
Mot de passe de récupération : `luks-build/RECOVERY_PASSWORD.txt` (à sauvegarder séparément — seul accès de secours si Tang devient injoignable)

## Difficultés rencontrées et résolues

- **URL image Raspberry Pi OS** : utiliser l'URL stable `raspios_lite_arm64_latest`, pas une URL versionnée qui devient vite obsolète
- **Montage des partitions source** : `kpartx` plus fiable que `losetup -P` sur Docker Desktop Mac
- **binfmt_misc cassé** : contourné via invocation explicite `/usr/bin/qemu-aarch64-static <binaire>` — attention, les scripts shell (`clevis`, `update-initramfs`) doivent être invoqués via `/bin/bash` en argument, pas directement
- **`/proc` et `/sys` non montés** : nécessaires dès l'installation des paquets (`cryptsetup-initramfs` régénère l'initramfs au moment de l'installation)
- **`fstab` avec PARTUUID obsolète** : la ligne `/boot/firmware` référence le PARTUUID de l'image source d'origine — doit être mise à jour avec le PARTUUID de la nouvelle partition boot créée, pas seulement la ligne `/`
- **Hash de mot de passe dans un script bash** : `$6$...` doit être entre guillemets simples, sinon bash interprète `$6` comme une variable positionnelle
- **Résidus loop devices/dmsetup persistants** : si une tentative échoue en cours de route, les périphériques peuvent rester "coincés" au niveau de la VM Docker Desktop malgré `docker rm` du conteneur — en dernier recours, redémarrer complètement Docker Desktop (Quit puis relance, pas juste "Restart") réinitialise la VM sous-jacente
