<?php
/**
 * Plugin Name: Scrawly Companion
 * Description: Minimal guarded endpoints for Scrawly (robots.txt, schema injection).
 * Version: 1.0.0
 * Author: The Run Digital
 */

if (!defined('ABSPATH')) {
    exit; // Exit if accessed directly
}

class Scrawly_Companion {
    
    public function __init__() {
        add_action('rest_api_init', [$this, 'register_endpoints']);
        
        // Hook into WP's virtual robots.txt generator
        add_filter('robots_txt', [$this, 'filter_robots_txt'], 99, 2);
    }
    
    public function register_endpoints() {
        register_rest_route('scrawly/v1', '/robots-txt', [
            'methods' => 'POST',
            'callback' => [$this, 'update_robots_txt'],
            'permission_callback' => [$this, 'check_permission']
        ]);
        
        register_rest_route('scrawly/v1', '/robots-txt', [
            'methods' => 'GET',
            'callback' => [$this, 'get_robots_txt'],
            'permission_callback' => [$this, 'check_permission']
        ]);
    }
    
    public function check_permission() {
        return current_user_can('manage_options');
    }
    
    public function update_robots_txt(WP_REST_Request $request) {
        $content = $request->get_param('content');
        
        if ($content === null) {
            return new WP_Error('missing_param', 'Missing content parameter.', ['status' => 400]);
        }
        
        $before = get_option('scrawly_robots_txt_custom', '');
        
        update_option('scrawly_robots_txt_custom', sanitize_textarea_field($content));
        
        return rest_ensure_response([
            'success' => true,
            'before_state' => $before,
            'after_state' => $content
        ]);
    }
    
    public function get_robots_txt(WP_REST_Request $request) {
        return rest_ensure_response([
            'content' => get_option('scrawly_robots_txt_custom', '')
        ]);
    }
    
    public function filter_robots_txt($output, $public) {
        $custom = get_option('scrawly_robots_txt_custom', '');
        if (!empty($custom)) {
            // Append or completely replace? The requirement is to manage lines.
            // For MVP, we'll append to WP's default virtual robots.txt.
            $output .= "\n\n# Added by Scrawly\n" . $custom;
        }
        return $output;
    }
}

$scrawly_companion = new Scrawly_Companion();
$scrawly_companion->__init__();
