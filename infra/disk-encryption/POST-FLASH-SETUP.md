# Remise en état après flashage de l'image chiffrée

Une fois l'image chiffrée (`face-recognition-pi-encrypted.img`) flashée et le
Pi démarré avec succès (SSH accessible), le système est "nu" — il faut
réinstaller Docker et reconnecter toute la chaîne CI/CD. Étapes dans l'ordre.

## 1. Agrandir la partition

L'image est construite petite (4 Go) pour des raisons de rapidité. Utilise
le reste de la carte SD :

```bash
sudo growpart /dev/mmcblk0 2
sudo cryptsetup resize cryptroot   # demande le mot de passe de récupération
                                    # (RECOVERY_PASSWORD.txt), PAS le mot de
                                    # passe SSH de l'utilisateur admin
sudo resize2fs /dev/mapper/cryptroot
df -h /
```

## 2. Installer Docker

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
exit
```

Reconnecte-toi en SSH pour appliquer le changement de groupe, puis vérifie :

```bash
docker --version
docker ps
```

## 3. Réautoriser la clé SSH de Jenkins

**Depuis ton Mac** (pas depuis le Pi) :

```bash
docker exec -u jenkins edgesentinel-jenkins cat /var/jenkins_home/.ssh/id_ed25519.pub | ssh admin@face-recognition-pi.local 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys'

docker exec -u jenkins edgesentinel-jenkins ssh-keygen -R face-recognition-pi.local

docker exec -u jenkins edgesentinel-jenkins ssh -i /var/jenkins_home/.ssh/id_ed25519 -o StrictHostKeyChecking=accept-new admin@face-recognition-pi.local "echo Connexion SSH automatisee reussie"
```

Le `ssh-keygen -R` est nécessaire car chaque nouveau flashage génère une
nouvelle clé d'hôte SSH — sans ce nettoyage, Jenkins refuse la connexion
("REMOTE HOST IDENTIFICATION HAS CHANGED").

## 4. Authentifier le Pi auprès de GitHub Container Registry

**Sur le Pi** :

```bash
echo "TON_TOKEN_READ_PACKAGES" | docker login ghcr.io -u kemgangchristian --password-stdin
docker pull ghcr.io/kemgangchristian/face-recognition-edge:latest
```

Si tu n'as plus le token (GitHub ne le réaffiche jamais après création),
supprime-le et régénère-en un nouveau sur
`https://github.com/settings/tokens` avec le scope `read:packages`
uniquement.

## 5. Vérifier/mettre à jour le hostname dans le Jenkinsfile

Si tu reviens d'un accès Tailscale précédent, le Jenkinsfile peut encore
pointer vers l'ancien nom `*.tailXXXXX.ts.net` (qui change à chaque
réinstallation de Tailscale). En attendant de reconfigurer Tailscale,
utilise le hostname local :

```groovy
PI_ADDRESS = 'face-recognition-pi.local'
```

## 6. Sécuriser l'accès SSH (clé uniquement, mot de passe désactivé)

**Étape critique** : vérifier que la connexion par clé fonctionne **avant**
de désactiver l'authentification par mot de passe — sinon risque de perdre
tout accès distant (récupérable seulement via accès physique).

### 6a. Copier ta clé publique vers le Pi

**Depuis ton Mac** :

```bash
ssh-copy-id admin@face-recognition-pi.local
```

*(Demande le mot de passe une dernière fois pour cette copie. Si tu n'as pas
encore de clé SSH sur ton Mac : `ssh-keygen -t ed25519` avant cette étape.)*

### 6b. Vérifier que la connexion par clé fonctionne SANS mot de passe

```bash
ssh admin@face-recognition-pi.local
```

Tu dois te connecter directement, sans qu'aucun mot de passe ne soit
demandé. **Ne continue à l'étape suivante que si c'est confirmé.**

### 6c. Désactiver l'authentification par mot de passe

**Sur le Pi** :

```bash
sudo nano /etc/ssh/sshd_config
```

Trouve (ou ajoute) ces lignes, en t'assurant qu'elles ne sont pas commentées
(pas de `#` au début) :

PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no

Sauvegarde, puis applique :

```bash
sudo systemctl restart ssh
```

### 6d. Vérifier que le mot de passe est bien bloqué

**Depuis un terminal différent** (garde ta session actuelle ouverte au cas
où, ne te déconnecte pas avant d'avoir confirmé) :

```bash
ssh -o PubkeyAuthentication=no admin@face-recognition-pi.local
```

Doit refuser la connexion (`Permission denied`) plutôt que de proposer un
mot de passe — confirmation que seule l'authentification par clé est
désormais acceptée.

### 6e. Réautoriser Jenkins après ce changement

Jenkins utilise déjà l'authentification par clé (configurée à l'étape 3),
donc cette désactivation du mot de passe **ne casse pas** le déploiement
automatisé — vérifie simplement que le prochain build Jenkins fonctionne
toujours normalement.

## 7. (Optionnel) Réinstaller Tailscale pour l'accès à distance

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Ouvre le lien affiché pour authentifier ce Pi sur ton compte Tailscale.
Le nouveau nom d'hôte (`*.tailXXXXX.ts.net`) sera différent de l'ancien —
mets à jour le Jenkinsfile en conséquence si tu veux déployer depuis
l'extérieur du réseau local.

## 8. Relancer le déploiement complet

**Jenkins** → job `face-recognition-iot` → **Build Now**

## 9. Vérification finale

```bash
docker ps
curl http://localhost:8000/health
```

Doit afficher le conteneur `Up` et `{"status":"ok"}`.

## Piège rencontré : espace disque insuffisant

Si le pull de l'image échoue avec `no space left on device` alors que
`df -h` semble montrer de l'espace libre : vérifie que l'étape 1
(agrandissement de partition) a bien été faite — une image chiffrée fraîche
non agrandie ne fait que ~4 Go, largement insuffisant pour l'image Docker
complète (~800 Mo) une fois l'OS de base pris en compte.