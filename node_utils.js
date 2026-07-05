const fs = require("fs");
const path = require("path");
const redis = require("@redis/client");
let bench_path;
if (process.env.FRAPPE_BENCH_ROOT) {
	bench_path = process.env.FRAPPE_BENCH_ROOT;
} else {
	bench_path = path.resolve(__dirname, "..", "..");
}

const dns = require("dns");

// Since node17, node resolves to ipv6 unless system is configured otherwise.
// In Frappe context using ipv4 - 127.0.0.1 is fine.
dns.setDefaultResultOrder("ipv4first");

function get_conf() {
	// defaults
	var conf = {
		socketio_port: 9000,
	};

	var read_config = function (file_path) {
		const full_path = path.resolve(bench_path, file_path);

		if (fs.existsSync(full_path)) {
			var bench_config = JSON.parse(fs.readFileSync(full_path));
			for (var key in bench_config) {
				if (bench_config[key]) {
					conf[key] = bench_config[key];
				}
			}
		}
	};

	// get ports from bench/config.json
	read_config("config.json");
	read_config("sites/common_site_config.json");

	// set overrides from environment
	if (process.env.FRAPPE_SITE) {
		conf.default_site = process.env.FRAPPE_SITE;
	}
	if (process.env.FRAPPE_REDIS_CACHE) {
		conf.redis_cache = process.env.FRAPPE_REDIS_CACHE;
	}
	if (process.env.FRAPPE_REDIS_QUEUE) {
		conf.redis_queue = process.env.FRAPPE_REDIS_QUEUE;
	}
	if (process.env.FRAPPE_SOCKETIO_PORT) {
		conf.socketio_port = process.env.FRAPPE_SOCKETIO_PORT;
	}
	if (process.env.FRAPPE_SOCKETIO_UDS) {
		conf.socketio_uds = process.env.FRAPPE_SOCKETIO_UDS;
	}
	return conf;
}

function get_redis_subscriber(kind = "redis_queue", options = {}) {
	const conf = get_conf();
	const connStr = conf[kind];
	// PR-Foundry fork patch (framework#67): make the realtime redis client
	// resilient to a transient redis blip (restart / network hiccup).
	//
	// 1. reconnectStrategy: reconnect on a transient blip (node-redis v4 restores
	//    subscriptions automatically on reconnect, so realtime self-heals), but
	//    GIVE UP after a bounded number of tries so a genuinely unreachable redis
	//    fails fast — retrying forever hangs `bench build`, which has no redis.
	// 2. an "error" handler: @redis/client emits "error" on a dropped/refused
	//    connection, and an UNHANDLED "error" on a Node EventEmitter is FATAL —
	//    it crashes the socketio process, which then sits dead (the container
	//    does not exit, so `restart: unless-stopped` never fires) until someone
	//    restarts it by hand. Handling it keeps the process alive to reconnect.
	//
	// Upstream-owned file: a frappe upstream-sync can reset this — re-verify
	// get_redis_subscriber still attaches the error handler after any sync.
	const { socket: socketOverrides, ...restOptions } = options;
	const socket = {
		// Reconnect on a transient blip (redis restart / network hiccup), but GIVE
		// UP after ~20 tries so a genuinely unreachable redis fails fast instead of
		// retrying forever. Retrying forever would HANG `bench build` (which has no
		// redis) — before this patch the unhandled error crashed that process and
		// the build tolerated it. On give-up the connect promise rejects and the
		// process exits, so the socketio container's restart policy recreates it
		// and retries fresh; a transient blip reconnects well within the window.
		reconnectStrategy: (retries) =>
			retries > 20
				? new Error("redis unreachable — giving up after 20 reconnect attempts")
				: Math.min(retries * 200, 2000),
		...(socketOverrides || {}),
	};
	let client;
	if (connStr && connStr.startsWith("unix://")) {
		client = redis.createClient({
			socket: { path: connStr.replace("unix://", ""), ...socket },
			...restOptions,
		});
	} else {
		client = redis.createClient({ url: connStr, socket, ...restOptions });
	}
	client.on("error", (err) => {
		console.error(`[frappe-realtime] redis(${kind}) client error:`, err?.message || err);
	});
	return client;
}

module.exports = {
	get_conf,
	get_redis_subscriber,
};
