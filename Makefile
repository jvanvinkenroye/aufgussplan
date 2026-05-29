.PHONY: build run scrape stats query help install-systemd

help:
	@echo "Aufgussplan Podman Commands:"
	@echo ""
	@echo "  make build    - Container-Image bauen"
	@echo "  make scrape   - Alle Standorte scrapen"
	@echo "  make stats    - Statistiken anzeigen"
	@echo "  make query    - Aufgüsse für heute"
	@echo ""
	@echo "Systemd:"
	@echo "  make install-systemd  - User-Service installieren"

build:
	podman build -t aufgussplan:latest -f Containerfile .

scrape:
	podman run --rm -v aufgussplan-data:/data:Z aufgussplan:latest \
		--db-file /data/aufgussplan.db --db --all

stats:
	podman run --rm -v aufgussplan-data:/data:Z aufgussplan:latest \
		--db-file /data/aufgussplan.db --db-stats

query:
	podman run --rm -v aufgussplan-data:/data:Z aufgussplan:latest \
		--db-file /data/aufgussplan.db --db-query heute

install-systemd:
	mkdir -p ~/.config/systemd/user
	cp systemd/aufgussplan.service ~/.config/systemd/user/
	cp systemd/aufgussplan.timer ~/.config/systemd/user/
	systemctl --user daemon-reload
	systemctl --user enable --now aufgussplan.timer
	@echo "Timer aktiviert. Status: systemctl --user status aufgussplan.timer"
