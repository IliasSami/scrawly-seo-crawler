<?php
/**
 * Plugin Name: Scrawly Connector
 * Description: Secure bridge that connects a WordPress site to Scrawly (technical-SEO auditor + guarded auto-fixer). Generates a connection key, exposes guarded REST endpoints, and WP-CLI commands. No file editing.
 * Version: 1.0.0
 * Author: The Run Digital
 * License: GPL-2.0-or-later
 * Requires at least: 5.6
 * Requires PHP: 7.4
 */

if (!defined('ABSPATH')) {
    exit; // No direct access.
}

class Scrawly_Connector {

    const VERSION      = '1.0.0';
    const NS           = 'scrawly/v1';
    const OPT_KEY      = 'scrawly_connection_key';
    const OPT_LASTSEEN = 'scrawly_last_connected';
    const OPT_ALLOW    = 'scrawly_allow_fixes';
    const OPT_ROBOTS   = 'scrawly_robots_custom';
    const OPT_REDIRECTS = 'scrawly_redirects';

    /** Logical SEO field -> [yoast_meta_key, rankmath_meta_key]. */
    private $field_map = array(
        'title'     => array('_yoast_wpseo_title', 'rank_math_title'),
        'meta_desc' => array('_yoast_wpseo_metadesc', 'rank_math_description'),
        'canonical' => array('_yoast_wpseo_canonical', 'rank_math_canonical_url'),
        'robots'    => array('_yoast_wpseo_meta-robots-noindex', 'rank_math_robots'),
    );

    public function __construct() {
        register_activation_hook(__FILE__, array($this, 'on_activate'));
        // Also ensure a key exists at load (covers mu-plugin installs where the
        // activation hook doesn't run).
        add_action('init', array($this, 'ensure_key'));
        add_action('rest_api_init', array($this, 'register_routes'));
        add_action('admin_menu', array($this, 'admin_menu'));
        add_action('admin_post_scrawly_regenerate', array($this, 'handle_regenerate'));
        add_action('admin_post_scrawly_toggle_fixes', array($this, 'handle_toggle_fixes'));
        add_filter('robots_txt', array($this, 'filter_robots_txt'), 99, 2);
        add_action('template_redirect', array($this, 'apply_redirects'), 1);
        if (defined('WP_CLI') && WP_CLI) {
            WP_CLI::add_command('scrawly', 'Scrawly_CLI');
        }
    }

    public function on_activate() {
        $this->ensure_key();
    }

    public function ensure_key() {
        if (!get_option(self::OPT_KEY)) {
            update_option(self::OPT_KEY, self::generate_key());
        }
        if (get_option(self::OPT_ALLOW) === false) {
            update_option(self::OPT_ALLOW, '1');
        }
    }

    public static function generate_key() {
        return 'sk_' . bin2hex(random_bytes(24)); // 51-char opaque key
    }

    // ------------------------------------------------------------------ auth
    /** Constant-time check of the connection key from header or query. */
    public function authorize(WP_REST_Request $request) {
        $stored = (string) get_option(self::OPT_KEY, '');
        $given  = $request->get_header('x_scrawly_key');
        if (!$given) {
            $auth = $request->get_header('authorization');
            if ($auth && stripos($auth, 'bearer ') === 0) {
                $given = trim(substr($auth, 7));
            }
        }
        if ($stored && $given && hash_equals($stored, (string) $given)) {
            update_option(self::OPT_LASTSEEN, gmdate('c'));
            return true;
        }
        return new WP_Error('scrawly_forbidden', 'Invalid or missing Scrawly connection key.', array('status' => 401));
    }

    private function fixes_allowed() {
        return get_option(self::OPT_ALLOW, '1') === '1';
    }

    // ---------------------------------------------------------------- routes
    public function register_routes() {
        $auth = array($this, 'authorize');
        $r = function ($path, $methods, $cb) use ($auth) {
            register_rest_route(self::NS, $path, array(
                'methods'             => $methods,
                'callback'            => array($this, $cb),
                'permission_callback' => $auth,
            ));
        };
        $r('/status',            'GET',    'route_status');
        $r('/seo-plugin',        'GET',    'route_seo_plugin');
        $r('/resolve',           'POST',   'route_resolve');
        $r('/post-meta/(?P<id>\\d+)', 'GET',  'route_get_meta');
        $r('/post-meta/(?P<id>\\d+)', 'POST', 'route_set_meta');
        $r('/redirects',         'GET',    'route_get_redirects');
        $r('/redirects',         'POST',   'route_add_redirect');
        $r('/redirects/(?P<id>\\d+)', 'DELETE', 'route_del_redirect');
        $r('/robots',            'GET',    'route_get_robots');
        $r('/robots',            'POST',   'route_set_robots');
        $r('/mcp',               'GET',    'route_mcp');
    }

    private function active_seo_plugin() {
        if (!function_exists('is_plugin_active')) {
            include_once ABSPATH . 'wp-admin/includes/plugin.php';
        }
        $yoast = is_plugin_active('wordpress-seo/wp-seo.php') || defined('WPSEO_VERSION');
        $rank  = is_plugin_active('seo-by-rank-math/rank-math.php') || defined('RANK_MATH_VERSION');
        if ($yoast && $rank) return 'both';
        if ($yoast) return 'yoast';
        if ($rank)  return 'rankmath';
        return 'none';
    }

    public function route_status() {
        return rest_ensure_response(array(
            'connected'        => true,
            'scrawly_version'  => self::VERSION,
            'site_url'         => home_url('/'),
            'wp_version'       => get_bloginfo('version'),
            'seo_plugin'       => $this->active_seo_plugin(),
            'fixes_allowed'    => $this->fixes_allowed(),
            'redirection_plugin' => is_plugin_active('redirection/redirection.php'),
        ));
    }

    public function route_seo_plugin() {
        return rest_ensure_response(array('seo_plugin' => $this->active_seo_plugin()));
    }

    public function route_resolve(WP_REST_Request $req) {
        $url = (string) $req->get_param('url');
        $post_id = url_to_postid($url);
        if (!$post_id) {
            // Fall back to ?p= / ?page_id= parsing.
            $q = wp_parse_url($url, PHP_URL_QUERY);
            if ($q) { parse_str($q, $args); foreach (array('p','page_id') as $k) { if (!empty($args[$k]) && is_numeric($args[$k])) { $post_id = (int) $args[$k]; break; } } }
        }
        return rest_ensure_response(array('post_id' => $post_id ? (int) $post_id : null));
    }

    private function meta_key_for($field) {
        $plugin = $this->active_seo_plugin();
        if (!isset($this->field_map[$field])) return null;
        return ($plugin === 'rankmath') ? $this->field_map[$field][1] : $this->field_map[$field][0];
    }

    public function route_get_meta(WP_REST_Request $req) {
        $id = (int) $req['id'];
        $post = get_post($id);
        if (!$post) return new WP_Error('not_found', 'Post not found.', array('status' => 404));
        $meta = array();
        foreach (array_keys($this->field_map) as $field) {
            $key = $this->meta_key_for($field);
            $meta[$field] = $key ? (string) get_post_meta($id, $key, true) : '';
        }
        $meta['post_title'] = get_the_title($id);
        return rest_ensure_response(array('id' => $id, 'meta' => $meta));
    }

    public function route_set_meta(WP_REST_Request $req) {
        if (!$this->fixes_allowed()) {
            return new WP_Error('fixes_disabled', 'Auto-fixes are disabled in Scrawly Connector settings.', array('status' => 403));
        }
        if ($this->active_seo_plugin() === 'both') {
            return new WP_Error('seo_conflict', 'Both Yoast and RankMath active; refusing to write meta (Check V06).', array('status' => 409));
        }
        $id = (int) $req['id'];
        if (!get_post($id)) return new WP_Error('not_found', 'Post not found.', array('status' => 404));
        $meta = (array) $req->get_param('meta');
        $before = array();
        $after  = array();
        foreach ($meta as $field => $value) {
            $key = $this->meta_key_for($field);
            if (!$key) continue; // only whitelisted SEO fields
            $before[$field] = (string) get_post_meta($id, $key, true);
            update_post_meta($id, $key, sanitize_text_field((string) $value));
            $after[$field] = (string) $value;
        }
        return rest_ensure_response(array('id' => $id, 'before' => $before, 'after' => $after));
    }

    // -- redirects (built-in, no dependency on the Redirection plugin) --------
    private function redirects() {
        $r = get_option(self::OPT_REDIRECTS, array());
        return is_array($r) ? $r : array();
    }

    public function route_get_redirects() {
        return rest_ensure_response(array('items' => array_values($this->redirects())));
    }

    public function route_add_redirect(WP_REST_Request $req) {
        if (!$this->fixes_allowed()) {
            return new WP_Error('fixes_disabled', 'Auto-fixes are disabled.', array('status' => 403));
        }
        $source = esc_url_raw((string) $req->get_param('source'));
        $target = esc_url_raw((string) $req->get_param('target'));
        $code   = (int) ($req->get_param('code') ?: 301);
        if (!$source || !$target) return new WP_Error('bad_request', 'source and target required.', array('status' => 400));
        $items = $this->redirects();
        $id = (int) (get_option('scrawly_redirect_seq', 0)) + 1;
        update_option('scrawly_redirect_seq', $id);
        $items[$id] = array('id' => $id, 'source' => $this->rel_path($source), 'target' => $target, 'code' => $code);
        update_option(self::OPT_REDIRECTS, $items);
        return rest_ensure_response(array('id' => $id));
    }

    public function route_del_redirect(WP_REST_Request $req) {
        $id = (int) $req['id'];
        $items = $this->redirects();
        unset($items[$id]);
        update_option(self::OPT_REDIRECTS, $items);
        return rest_ensure_response(array('deleted' => true));
    }

    private function rel_path($url) {
        $p = wp_parse_url($url, PHP_URL_PATH);
        return $p ? $p : $url;
    }

    public function apply_redirects() {
        if (is_admin()) return;
        $req = isset($_SERVER['REQUEST_URI']) ? wp_parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH) : '';
        foreach ($this->redirects() as $rule) {
            if (untrailingslashit($rule['source']) === untrailingslashit($req)) {
                wp_redirect($rule['target'], (int) $rule['code']);
                exit;
            }
        }
    }

    // -- robots.txt line management (guarded; never edits files) --------------
    public function route_get_robots() {
        return rest_ensure_response(array('content' => (string) get_option(self::OPT_ROBOTS, '')));
    }

    public function route_set_robots(WP_REST_Request $req) {
        if (!$this->fixes_allowed()) {
            return new WP_Error('fixes_disabled', 'Auto-fixes are disabled.', array('status' => 403));
        }
        $before = (string) get_option(self::OPT_ROBOTS, '');
        update_option(self::OPT_ROBOTS, sanitize_textarea_field((string) $req->get_param('content')));
        return rest_ensure_response(array('before' => $before, 'after' => (string) $req->get_param('content')));
    }

    public function filter_robots_txt($output, $public) {
        $custom = (string) get_option(self::OPT_ROBOTS, '');
        if ($custom !== '') $output .= "\n# Managed by Scrawly\n" . $custom . "\n";
        return $output;
    }

    /** Lightweight tool manifest for MCP-style discovery. */
    public function route_mcp() {
        return rest_ensure_response(array(
            'name' => 'scrawly-connector',
            'version' => self::VERSION,
            'base' => rest_url(self::NS),
            'auth' => 'X-Scrawly-Key header',
            'tools' => array(
                array('name' => 'status', 'method' => 'GET',  'path' => '/status'),
                array('name' => 'resolve_post', 'method' => 'POST', 'path' => '/resolve', 'args' => array('url')),
                array('name' => 'get_seo_meta', 'method' => 'GET', 'path' => '/post-meta/{id}'),
                array('name' => 'set_seo_meta', 'method' => 'POST', 'path' => '/post-meta/{id}', 'args' => array('meta')),
                array('name' => 'create_redirect', 'method' => 'POST', 'path' => '/redirects', 'args' => array('source','target','code')),
            ),
        ));
    }

    // ----------------------------------------------------------------- admin
    public function admin_menu() {
        add_menu_page('Scrawly', 'Scrawly', 'manage_options', 'scrawly-connector', array($this, 'admin_page'), 'dashicons-search', 80);
    }

    public function admin_page() {
        if (!current_user_can('manage_options')) return;
        $key = (string) get_option(self::OPT_KEY, '');
        $last = get_option(self::OPT_LASTSEEN, '');
        $allow = $this->fixes_allowed();
        ?>
        <div class="wrap">
          <h1>Scrawly Connector</h1>
          <p>Connect this site to Scrawly. Paste the <strong>Site URL</strong> and <strong>Connection Key</strong> into Scrawly &rarr; Settings.</p>
          <table class="form-table" role="presentation">
            <tr><th>Site URL</th><td><code><?php echo esc_html(home_url('/')); ?></code></td></tr>
            <tr><th>Connection Key</th><td>
              <input type="text" readonly value="<?php echo esc_attr($key); ?>" style="width:420px;font-family:monospace" onclick="this.select()">
              <form method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>" style="display:inline">
                <input type="hidden" name="action" value="scrawly_regenerate">
                <?php wp_nonce_field('scrawly_regenerate'); ?>
                <button class="button" onclick="return confirm('Regenerate the key? Scrawly will need the new key to reconnect.')">Regenerate</button>
              </form>
            </td></tr>
            <tr><th>Last connected</th><td><?php echo $last ? esc_html($last) : '&mdash; not yet'; ?></td></tr>
            <tr><th>Allow auto-fixes</th><td>
              <form method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>">
                <input type="hidden" name="action" value="scrawly_toggle_fixes">
                <?php wp_nonce_field('scrawly_toggle_fixes'); ?>
                <label><input type="checkbox" name="allow" value="1" <?php checked($allow); ?>> Let Scrawly apply guarded fixes (titles, meta, canonical, redirects). Never edits files.</label>
                <p><button class="button button-primary">Save</button></p>
              </form>
            </td></tr>
            <tr><th>SEO plugin detected</th><td><code><?php echo esc_html($this->active_seo_plugin()); ?></code></td></tr>
          </table>
        </div>
        <?php
    }

    public function handle_regenerate() {
        if (!current_user_can('manage_options') || !check_admin_referer('scrawly_regenerate')) wp_die('Denied');
        update_option(self::OPT_KEY, self::generate_key());
        wp_safe_redirect(admin_url('admin.php?page=scrawly-connector'));
        exit;
    }

    public function handle_toggle_fixes() {
        if (!current_user_can('manage_options') || !check_admin_referer('scrawly_toggle_fixes')) wp_die('Denied');
        update_option(self::OPT_ALLOW, isset($_POST['allow']) ? '1' : '0');
        wp_safe_redirect(admin_url('admin.php?page=scrawly-connector'));
        exit;
    }
}

if (defined('WP_CLI') && WP_CLI) {
    class Scrawly_CLI {
        /** Show the connection key. */
        public function key($args, $assoc) {
            if (!empty($assoc['regenerate'])) {
                update_option(Scrawly_Connector::OPT_KEY, Scrawly_Connector::generate_key());
                WP_CLI::success('Key regenerated.');
            }
            WP_CLI::line(get_option(Scrawly_Connector::OPT_KEY, ''));
        }
        /** Show connection status. */
        public function status() {
            WP_CLI::line('Site: ' . home_url('/'));
            WP_CLI::line('Last connected: ' . (get_option(Scrawly_Connector::OPT_LASTSEEN) ?: 'never'));
            WP_CLI::line('Fixes allowed: ' . (get_option(Scrawly_Connector::OPT_ALLOW, '1') === '1' ? 'yes' : 'no'));
        }
    }
}

new Scrawly_Connector();
