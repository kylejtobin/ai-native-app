# Installation Guide

**Get the AI-native stack running on your machine in under 5 minutes.**

This guide covers installation on Linux, macOS, and Windows. The stack uses Docker for consistency across all platforms—same environment everywhere.

---

## Prerequisites

You need three things:

1. **Docker** (includes Docker Compose v2)
2. **Make** (task automation)
3. **Git** (to clone the repository)

### Linux (Ubuntu/Debian)

```bash
# Update package list
sudo apt update

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker  # Activate group without logout

# Install Make and Git
sudo apt install -y make git

# Verify installations
docker --version
docker compose version  # Note: 'docker compose' not 'docker-compose'
make --version
git --version
```

**Other Linux distributions:**
- **Fedora/RHEL/CentOS:** `sudo dnf install docker make git`
- **Arch:** `sudo pacman -S docker make git`

**Enable Docker on boot:**
```bash
sudo systemctl enable docker
sudo systemctl start docker
```

### macOS

**Option 1: Docker Desktop (Recommended)**

1. Download [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
2. Install the `.dmg` file
3. Start Docker Desktop from Applications

Docker Desktop includes Docker Compose and Make. Install Git if needed:

```bash
# Using Homebrew
brew install git

# Verify installations
docker --version
docker compose version
make --version
git --version
```

**Option 2: Homebrew (Advanced)**

```bash
# Install Docker via Homebrew (requires additional setup)
brew install docker docker-compose make git

# Follow Homebrew's post-install instructions for Docker
```

### Windows

**Use WSL2 (Windows Subsystem for Linux) - Recommended**

Docker works best on Windows via WSL2. This gives you a real Linux environment.

**Step 1: Enable WSL2**

```powershell
# Run in PowerShell as Administrator
wsl --install
```

This installs WSL2 and Ubuntu by default. Restart your computer.

**Step 2: Install Docker Desktop**

1. Download [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. During installation, ensure "Use WSL 2 instead of Hyper-V" is checked
3. Start Docker Desktop
4. In Docker Desktop settings, enable "Use the WSL 2 based engine"

**Step 3: Install tools in WSL2**

Open Ubuntu from Start Menu, then:

```bash
# Update package list
sudo apt update

# Install Make and Git (Docker is already available via Docker Desktop)
sudo apt install -y make git

# Verify installations
docker --version
docker compose version
make --version
git --version
```

**Alternative: Git Bash (Not Recommended)**

If you must avoid WSL2, you can use Git Bash:
1. Install [Git for Windows](https://git-scm.com/download/win) (includes Git Bash)
2. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
3. Install [Make for Windows](https://gnuwin32.sourceforge.net/packages/make.htm)

However, **WSL2 is strongly recommended** for the best experience.

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ai-native-app-architecture.git
cd ai-native-app-architecture
```

### 2. Add API Keys (Optional but Recommended)

The stack works without API keys (using local models), but for full functionality:

```bash
# Create secrets directory
mkdir -p secrets/api

# Add your API keys (one per file, no quotes)
echo "sk-ant-your-key-here" > secrets/api/anthropic
echo "sk-your-key-here" > secrets/api/openai
echo "tvly-your-key-here" > secrets/api/tavily

# Keys are git-ignored, never committed
```

**Don't have API keys?** The stack still works! Ollama provides local LLM inference.

### 3. Start the Stack

```bash
# Generate config and start all services
make dev
```

**What happens:**
1. Generates `.env` from template
2. Loads your API keys (if present)
3. Generates random passwords for databases
4. Starts 7 containers (PostgreSQL, Redis, Neo4j, Qdrant, MinIO, Ollama, FastAPI)
5. Runs initialization scripts (databases, buckets)
6. Shows "✅ Services ready"

**First run takes 2-3 minutes** (downloading images). Subsequent starts take ~10 seconds.

### 4. Verify Installation

Open your browser to verify services:

- **API**: http://localhost:8000
- **API Docs** (Swagger): http://localhost:8000/docs
- **Neo4j Browser**: http://localhost:7474 (login: `neo4j`, password: see `.env`)
- **MinIO Console**: http://localhost:9001 (credentials: see `.env`)

**Check service status:**
```bash
docker compose ps
# All services should show "healthy" or "running"
```

---

## Common Commands

```bash
# Start stack (generate config + start services)
make dev

# Stop stack (keep data)
make down

# Restart stack (after config changes)
make restart

# View logs (all services)
make logs

# View logs (specific service)
docker compose logs api
docker compose logs postgres

# Full reset (delete all data)
make clean

# Complete rebuild (clean + dev)
make rebuild

# Database shell (PostgreSQL)
make shell-db

# Show all commands
make help
```

See the [`Makefile`](../Makefile) for all available commands.

---

## Troubleshooting

### "Command 'docker' not found"

**Cause:** Docker not installed or not in PATH

**Fix:**
```bash
# Linux: Install Docker
curl -fsSL https://get.docker.com | sh

# macOS/Windows: Install Docker Desktop
# Then restart terminal
```

### "Permission denied" (Linux only)

**Cause:** User not in `docker` group

**Fix:**
```bash
sudo usermod -aG docker $USER
newgrp docker  # Or logout and login again
```

### "Port already allocated"

**Cause:** Another service using the port (5432, 6379, 8000, etc.)

**Fix:**
```bash
# Find what's using the port
sudo lsof -i :5432
sudo netstat -tulpn | grep 5432

# Stop the conflicting service, then try again
make dev
```

### "Cannot connect to Docker daemon"

**Cause:** Docker service not running

**Fix:**
```bash
# Linux
sudo systemctl start docker

# macOS/Windows
# Start Docker Desktop from Applications/Start Menu
```

### Services not starting (stuck at "Starting...")

**Cause:** Previous containers still running with old project name

**Fix:**
```bash
# Stop ALL Docker containers
docker stop $(docker ps -q)

# Remove old containers
docker container prune -f

# Try again
make dev
```

### "No space left on device"

**Cause:** Docker images/volumes consuming disk space

**Fix:**
```bash
# Clean up unused images
docker image prune -a

# Clean up unused volumes
docker volume prune

# Nuclear option: clean everything
docker system prune -a --volumes
```

### Make commands not working (Windows)

**Cause:** Using Command Prompt or PowerShell instead of WSL2

**Fix:**
- Use WSL2 Ubuntu (recommended)
- OR use Git Bash (if you installed Make for Windows)
- Command Prompt/PowerShell don't support Makefiles

---

## Platform-Specific Notes

### Linux

✅ **Best experience** - Docker is native to Linux  
✅ **Fastest performance** - No virtualization overhead  
✅ **All features work** - Full Docker API support

**Recommendation:** Ubuntu 20.04+ or Debian 11+ for best compatibility

### macOS

✅ **Good experience** - Docker Desktop is mature  
⚠️ **Slight overhead** - Docker runs in a lightweight VM  
⚠️ **File sync** - Bind mounts (volume mounts) can be slower than Linux

**Recommendation:** macOS 11+ with Apple Silicon (M1/M2) or Intel

**Performance tip:** Use named volumes instead of bind mounts for better performance (already configured in `docker-compose.yml`)

### Windows

✅ **Excellent via WSL2** - Near-native Linux performance  
⚠️ **WSL2 required** - Hyper-V mode is deprecated  
❌ **Git Bash struggles** - Path translation issues, slow performance

**Recommendation:** Windows 10 (build 19041+) or Windows 11 with WSL2

**Path note:** When using WSL2, work inside `/home/username/` (Linux filesystem) for best performance. Avoid `/mnt/c/` (Windows filesystem mounted in WSL).

---

## Next Steps

Once installed:

1. **Explore the API**: http://localhost:8000/docs
2. **Try a conversation**: POST to `/conversations` with a message
3. **Read the architecture**: See [`docs/app/`](app/) for application patterns
4. **Understand infrastructure**: See [`docs/infra/`](infra/) for system details

**New to Docker?** Start with:
- [Infrastructure as Code](infra/iac.md) - Docker and containers explained
- [Orchestration](infra/orchestration.md) - How everything starts up
- [Systems](infra/systems.md) - What each database does

**Need help?** Check:
- [`README.md`](../README.md) - Architecture overview
- [`Makefile`](../Makefile) - All available commands
- [GitHub Issues](https://github.com/yourusername/ai-native-app-architecture/issues) - Known issues and solutions