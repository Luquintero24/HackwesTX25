#include <iostream>
#include <vector>
#include <string>
#include <map>
#include <cmath>
#include <limits>
#include <algorithm>
#include <queue>
#include <sstream>
#include <cstdlib>
#include <ctime>
#include <fstream>
#include <set>

#include <imgui.h>
#include <imgui_impl_glfw.h>
#include <imgui_impl_opengl3.h>
#include <GLFW/glfw3.h>

// Data Structures
struct Node {
    ImVec2 position;
    std::string label;
    bool selected = false;
    bool dragging = false;
    ImVec2 drag_offset;
    float radius;
    int connection_count = 0;
};

struct Edge {
    int from, to;
    std::string predicate;
};

// Struct for raw data from file
struct Triple {
    std::string node_name;
    std::string edge_name;
    std::string name_of_component;
    std::string severity;
};

// Helper function to convert severity to a numerical weight with more variability
float severityToWeight(const std::string& severity) {
    if (severity == "high") return 0.8f;
    if (severity == "medium") return 0.4f;
    if (severity == "low") return 0.1f;
    return 0.0f;
}

class GraphVisualizer {
private:
    std::vector<Node> nodes;
    std::vector<Edge> edges;
    std::vector<std::vector<float>> adjacency_matrix;
    std::vector<std::set<int>> adjacency_list;
    std::map<int, float> page_rank_scores;
    int selected_node = -1;
    std::vector<ImVec2> velocities;
    ImVec2 pan_offset = ImVec2(0.0f, 0.0f);
    bool is_panning = false;
    ImVec2 pan_drag_start_screen = ImVec2(0,0);
    ImVec2 pan_offset_start = ImVec2(0,0);
    ImFont* large_font = nullptr;
    float page_rank_average = 0.0f;
    float page_rank_std_dev = 0.0f;

public:
    GraphVisualizer() {
        srand(static_cast<unsigned int>(time(0)));
    }

    void setLargeFont(ImFont* font) {
        large_font = font;
    }

    void LoadTriples(const std::vector<Triple>& triples) {
        nodes.clear();
        edges.clear();
        velocities.clear();
        selected_node = -1;
        pan_offset = ImVec2(0.0f, 0.0f);
        page_rank_scores.clear();

        std::map<std::string, int> node_map;
        int next_node_index = 0;

        for (const auto& triple : triples) {
            if (node_map.find(triple.node_name) == node_map.end()) {
                node_map[triple.node_name] = next_node_index++;
                Node node;
                node.label = triple.node_name;
                nodes.push_back(node);
            }
            if (node_map.find(triple.name_of_component) == node_map.end()) {
                node_map[triple.name_of_component] = next_node_index++;
                Node node;
                node.label = triple.name_of_component;
                nodes.push_back(node);
            }
        }

        int n = nodes.size();
        adjacency_matrix.assign(n, std::vector<float>(n, 0.0f));
        adjacency_list.assign(n, std::set<int>());
        velocities.assign(n, ImVec2(0, 0));

        for (int i = 0; i < n; i++) {
            nodes[i].position = ImVec2(100.0f + (std::rand() % 600), 100.0f + (std::rand() % 400));
        }

        for (auto& node : nodes) {
            node.connection_count = 0;
        }

        for (const auto& triple : triples) {
            int from_idx = node_map[triple.node_name];
            int to_idx = node_map[triple.name_of_component];
            if (from_idx != to_idx) {
                edges.push_back({from_idx, to_idx, triple.edge_name});
                float weight = severityToWeight(triple.severity);
                adjacency_matrix[from_idx][to_idx] = weight;
                adjacency_matrix[to_idx][from_idx] = weight;

                adjacency_list[from_idx].insert(to_idx);
                adjacency_list[to_idx].insert(from_idx);
                
                nodes[from_idx].connection_count++;
                nodes[to_idx].connection_count++;
            }
        }

        int max_connections = 0;
        for (const auto& node : nodes) {
            if (node.connection_count > max_connections) {
                max_connections = node.connection_count;
            }
        }

        for (auto& node : nodes) {
            if (max_connections > 0) {
                node.radius = 25.0f + 25.0f * (static_cast<float>(node.connection_count) / max_connections);
            } else {
                node.radius = 25.0f;
            }
        }
    }

    void calculatePageRank() {
        int n = nodes.size();
        if (n == 0) return;

        float damping_factor = 0.85f;
        float initial_rank = 1.0f / n;
        std::map<int, float> current_ranks;
        std::map<int, float> new_ranks;
        std::map<int, int> out_degree;

        for (int i = 0; i < n; ++i) {
            current_ranks[i] = initial_rank;
            out_degree[i] = adjacency_list[i].size();
        }

        for (int iter = 0; iter < 20; ++iter) {
            for (int i = 0; i < n; ++i) {
                new_ranks[i] = 1.0f - damping_factor;
            }

            for (int i = 0; i < n; ++i) {
                for (int neighbor_idx : adjacency_list[i]) {
                    if (out_degree[i] > 0) {
                        new_ranks[neighbor_idx] += damping_factor * (current_ranks[i] / out_degree[i]);
                    }
                }
            }
            current_ranks = new_ranks;
        }
        
        float sum = 0.0f;
        for (const auto& pair : current_ranks) {
            sum += pair.second;
        }
        page_rank_average = sum / n;
        
        float variance_sum = 0.0f;
        for (const auto& pair : current_ranks) {
            variance_sum += pow(pair.second - page_rank_average, 2);
        }
        page_rank_std_dev = sqrt(variance_sum / n);
        
        page_rank_scores = current_ranks;
    }

    std::string getPageRankMeaning(float score) {
        if (page_rank_std_dev == 0) {
            return "Medium"; 
        }
    
        if (score > page_rank_average + page_rank_std_dev) {
            return "High";
        }
        if (score < page_rank_average - page_rank_std_dev) {
            return "Low";
        }
        return "Medium";
    }

    std::vector<std::pair<int, float>> predictLinksForNode(int node_index) {
        std::vector<std::pair<int, float>> predictions;
        if (node_index < 0 || node_index >= nodes.size()) {
            return predictions;
        }

        // Using Adamic-Adar Index for more variability
        std::map<int, float> adamic_adar_scores;
        
        const auto& neighbors = adjacency_list[node_index];

        for (int neighbor_idx : neighbors) {
            const auto& grand_neighbors = adjacency_list[neighbor_idx];
            for (int grand_neighbor_idx : grand_neighbors) {
                if (grand_neighbor_idx != node_index && neighbors.find(grand_neighbor_idx) == neighbors.end()) {
                    if (adjacency_list[grand_neighbor_idx].size() > 1) {
                         adamic_adar_scores[grand_neighbor_idx] += 1.0f / log(adjacency_list[grand_neighbor_idx].size());
                    } else {
                        adamic_adar_scores[grand_neighbor_idx] += 1.0f;
                    }
                }
            }
        }
        
        float max_score = 0.0f;
        for (const auto& pair : adamic_adar_scores) {
            if (pair.second > max_score) {
                max_score = pair.second;
            }
        }

        if (max_score > 0) {
            for (const auto& pair : adamic_adar_scores) {
                float normalized_score = pair.second / max_score;
                predictions.push_back({pair.first, normalized_score});
            }
        }
        
        std::sort(predictions.begin(), predictions.end(), [](const std::pair<int, float>& a, const std::pair<int, float>& b) {
            return a.second > b.second;
        });

        return predictions;
    }

    std::string getConceptualMeaning(float score) {
        if (score >= 0.8f) return "Strong";
        if (score >= 0.5f) return "Moderate";
        if (score >= 0.0f) return "Weak";
        return "";
    }

    void UpdatePhysics() {
        float time_step = 0.5f;
        float repulsion_strength = 2000.0f;
        float attraction_strength = 0.02f;
        float damping = 0.9f;

        for (int i = 0; i < nodes.size(); ++i) {
            if (nodes[i].dragging) continue;
            for (int j = i + 1; j < nodes.size(); ++j) {
                if (nodes[j].dragging) continue;
                ImVec2 delta = ImVec2(nodes[i].position.x - nodes[j].position.x, nodes[i].position.y - nodes[j].position.y);
                float dist_sq = delta.x * delta.x + delta.y * delta.y;
                if (dist_sq < 1.0f) dist_sq = 1.0f;
                float force = repulsion_strength / dist_sq;
                
                float dist = sqrtf(dist_sq);
                ImVec2 force_vector = ImVec2(delta.x / dist * force, delta.y / dist * force);
                
                velocities[i].x += force_vector.x;
                velocities[i].y += force_vector.y;
                velocities[j].x -= force_vector.x;
                velocities[j].y -= force_vector.y;
            }
        }

        for (const auto& edge : edges) {
            ImVec2 delta = ImVec2(nodes[edge.to].position.x - nodes[edge.from].position.x, nodes[edge.to].position.y - nodes[edge.from].position.y);
            float dist = sqrtf(delta.x * delta.x + delta.y * delta.y);
            if (dist < 1.0f) dist = 1.0f;
            float force = (dist - 100.0f) * attraction_strength;
            
            ImVec2 force_vector = ImVec2(delta.x / dist * force, delta.y / dist * force);
            
            if (!nodes[edge.from].dragging) {
                velocities[edge.from].x += force_vector.x;
                velocities[edge.from].y += force_vector.y;
            }
            if (!nodes[edge.to].dragging) {
                velocities[edge.to].x -= force_vector.x;
                velocities[edge.to].y -= force_vector.y;
            }
        }

        for (int i = 0; i < nodes.size(); ++i) {
            if (!nodes[i].dragging) {
                nodes[i].position.x += velocities[i].x * time_step;
                nodes[i].position.y += velocities[i].y * time_step;
                velocities[i].x *= damping;
                velocities[i].y *= damping;
            }
        }
    }

    void Render() {
        ImGui::Begin("Graph Visualizer", nullptr, ImGuiWindowFlags_MenuBar);
        if (ImGui::Button("Reset Layout")) {
            int n = nodes.size();
            for (int i = 0; i < n; i++) {
                nodes[i].position = ImVec2(100.0f + (std::rand() % 600), 100.0f + (std::rand() % 400));
                velocities[i] = ImVec2(0, 0);
            }
            selected_node = -1;
            pan_offset = ImVec2(0.0f, 0.0f);
        }
        ImGui::SameLine();
        if (ImGui::Button("Clear Selection")) {
            selected_node = -1;
            for (auto& n : nodes) n.selected = false;
        }
        ImGui::SameLine();
        ImGui::TextDisabled("(Pan: left-drag on empty space / right-drag / two-finger trackpad)");
        ImGui::Separator();
        ImVec2 canvas_pos = ImGui::GetCursorScreenPos();
        ImVec2 canvas_size = ImGui::GetContentRegionAvail();
        float summary_width = 300.0f;
        ImVec2 main_canvas_size = ImVec2(canvas_size.x - summary_width, canvas_size.y);
        ImGui::BeginChild("##MainCanvas", main_canvas_size, false, ImGuiWindowFlags_NoScrollbar | ImGuiWindowFlags_NoMove);
        ImDrawList* draw_list = ImGui::GetWindowDrawList();
        draw_list->AddRectFilled(ImGui::GetCursorScreenPos(), ImVec2(ImGui::GetCursorScreenPos().x + main_canvas_size.x, ImGui::GetCursorScreenPos().y + main_canvas_size.y), IM_COL32(255, 255, 255, 255));
        draw_list->AddRect(ImGui::GetCursorScreenPos(), ImVec2(ImGui::GetCursorScreenPos().x + main_canvas_size.x, ImGui::GetCursorScreenPos().y + main_canvas_size.y), IM_COL32(180, 180, 180, 255));
        ImVec2 mouse_pos = ImGui::GetMousePos();
        ImGuiIO& io = ImGui::GetIO();
        bool mouse_left_clicked = ImGui::IsMouseClicked(0);
        bool mouse_right_clicked = ImGui::IsMouseClicked(1);
        bool mouse_released = ImGui::IsMouseReleased(0);
        bool mouse_dragging_left = ImGui::IsMouseDragging(0);
        bool mouse_dragging_right = ImGui::IsMouseDragging(1);
        auto world_to_screen = [&](const ImVec2& world) -> ImVec2 {
            return ImVec2(ImGui::GetCursorScreenPos().x + world.x + pan_offset.x, ImGui::GetCursorScreenPos().y + world.y + pan_offset.y);
        };
        auto screen_to_world = [&](const ImVec2& screen) -> ImVec2 {
            return ImVec2((screen.x - ImGui::GetCursorScreenPos().x) - pan_offset.x, (screen.y - ImGui::GetCursorScreenPos().y) - pan_offset.y);
        };
        if (io.MouseWheel != 0.0f || io.MouseWheelH != 0.0f) {
            pan_offset.x += io.MouseWheelH * 30.0f;
            pan_offset.y += io.MouseWheel * 30.0f;
        }
        int hover_node = -1;
        bool mouse_in_canvas = (mouse_pos.x >= ImGui::GetCursorScreenPos().x && mouse_pos.x <= ImGui::GetCursorScreenPos().x + main_canvas_size.x && mouse_pos.y >= ImGui::GetCursorScreenPos().y && mouse_pos.y <= ImGui::GetCursorScreenPos().y + main_canvas_size.y);
        for (int i = 0; i < (int)nodes.size(); ++i) {
            ImVec2 node_screen_pos = world_to_screen(nodes[i].position);
            float dist_to_mouse = sqrtf(pow(mouse_pos.x - node_screen_pos.x, 2) + pow(mouse_pos.y - node_screen_pos.y, 2));
            if (dist_to_mouse < nodes[i].radius) {
                hover_node = i;
                break;
            }
        }
        if (mouse_left_clicked && mouse_in_canvas && hover_node == -1) {
            is_panning = true;
            pan_drag_start_screen = mouse_pos;
            pan_offset_start = pan_offset;
        }
        if (mouse_right_clicked && mouse_in_canvas && hover_node == -1) {
            is_panning = true;
            pan_drag_start_screen = mouse_pos;
            pan_offset_start = pan_offset;
        }
        if (is_panning && (mouse_dragging_left || mouse_dragging_right)) {
            ImVec2 delta = ImVec2(mouse_pos.x - pan_drag_start_screen.x, mouse_pos.y - pan_drag_start_screen.y);
            pan_offset = ImVec2(pan_offset_start.x + delta.x, pan_offset_start.y + delta.y);
        }
        if (is_panning && mouse_released && !ImGui::IsMouseDown(1)) {
            is_panning = false;
        }
        if (is_panning && !ImGui::IsMouseDown(0) && !ImGui::IsMouseDown(1)) {
            is_panning = false;
        }
        for (const auto& edge : edges) {
            ImVec2 p1 = world_to_screen(nodes[edge.from].position);
            ImVec2 p2 = world_to_screen(nodes[edge.to].position);
            ImU32 color = IM_COL32(0, 0, 0, 255);
            float draw_thickness = 1.5f;
            draw_list->AddLine(p1, p2, color, draw_thickness);
            ImVec2 mid_point = ImVec2((p1.x + p2.x) / 2.0f, (p1.y + p2.y) / 2.0f);
            ImVec2 text_size = ImGui::CalcTextSize(edge.predicate.c_str());
            ImVec2 text_pos = ImVec2(mid_point.x - text_size.x / 2.0f, mid_point.y - text_size.y / 2.0f);
            draw_list->AddText(text_pos, IM_COL32(0, 0, 0, 255), edge.predicate.c_str());
        }

        int max_connections = 0;
        if (!nodes.empty()) {
            for (const auto& node : nodes) {
                if (node.connection_count > max_connections) {
                    max_connections = node.connection_count;
                }
            }
        }

        for (int i = 0; i < (int)nodes.size(); ++i) {
            ImVec2 node_screen_pos = world_to_screen(nodes[i].position);
            float dist_to_mouse = sqrtf(pow(mouse_pos.x - node_screen_pos.x, 2) + pow(mouse_pos.y - node_screen_pos.y, 2));
            bool mouse_over_node = dist_to_mouse < nodes[i].radius;
            if (mouse_left_clicked && mouse_over_node && !nodes[i].dragging) {
                nodes[i].dragging = true;
                nodes[i].drag_offset = ImVec2(mouse_pos.x - node_screen_pos.x, mouse_pos.y - node_screen_pos.y);
                selected_node = i;
                for (auto& n : nodes) n.selected = false;
                nodes[i].selected = true;
                is_panning = false;
            }
            if (nodes[i].dragging) {
                if (mouse_dragging_left) {
                    ImVec2 raw_world = screen_to_world(ImVec2(mouse_pos.x, mouse_pos.y));
                    nodes[i].position = ImVec2(raw_world.x - nodes[i].drag_offset.x, raw_world.y - nodes[i].drag_offset.y);
                }
                else if (mouse_released) {
                    nodes[i].dragging = false;
                }
            }
            float normalized_connections = max_connections > 0 ? static_cast<float>(nodes[i].connection_count) / max_connections : 0.0f;

            ImU32 node_color;
            if (nodes[i].selected) {
                node_color = IM_COL32(100, 200, 100, 255);
            } else {
                if (normalized_connections < 0.33) {
                    node_color = IM_COL32(173, 216, 230, 255); // Light Blue
                } else if (normalized_connections < 0.66) {
                    node_color = IM_COL32(255, 165, 0, 255); // Orange
                } else {
                    node_color = IM_COL32(255, 0, 0, 255); // Red
                }

                if (mouse_over_node) {
                    node_color = ImGui::ColorConvertFloat4ToU32(ImVec4(
                        (float)ImGui::ColorConvertU32ToFloat4(node_color).x * 0.8f,
                        (float)ImGui::ColorConvertU32ToFloat4(node_color).y * 0.8f,
                        (float)ImGui::ColorConvertU32ToFloat4(node_color).z * 0.8f,
                        1.0f));
                    }
            }

            float min_radius = 15.0f;
            float max_radius = 40.0f;
            nodes[i].radius = min_radius + (max_radius - min_radius) * normalized_connections;
            if (nodes[i].radius < min_radius) nodes[i].radius = min_radius;

            draw_list->AddCircleFilled(node_screen_pos, nodes[i].radius, node_color);
            draw_list->AddCircle(node_screen_pos, nodes[i].radius, IM_COL32(0, 0, 0, 255), 0, 2.0f);
            std::string label = nodes[i].label;
            ImVec2 text_size = ImGui::CalcTextSize(label.c_str());
            ImVec2 text_pos = ImVec2(node_screen_pos.x - text_size.x / 2.0f, node_screen_pos.y - text_size.y / 2.0f);
            draw_list->AddText(text_pos, IM_COL32(0, 0, 0, 255), label.c_str());
        }
        ImGui::SetCursorPos(ImVec2(10, ImGui::GetWindowHeight() - 120));
        ImGui::BeginChild("InfoPanel", ImVec2(320, 110), true);
        if (selected_node >= 0 && selected_node < (int)nodes.size()) {
            ImGui::Text("Selected: %s", nodes[selected_node].label.c_str());
            ImGui::Text("Connections: %d", nodes[selected_node].connection_count);
            ImGui::Text("Position (world): (%.1f, %.1f)", nodes[selected_node].position.x, nodes[selected_node].position.y);
            ImGui::Text("Connected to:");
            bool first = true;
            for (const auto& e : edges) {
                if (e.from == selected_node) {
                    if (!first) ImGui::SameLine();
                    ImGui::Text("%s via '%s'", nodes[e.to].label.c_str(), e.predicate.c_str());
                    first = false;
                } else if (e.to == selected_node) {
                    if (!first) ImGui::SameLine();
                    ImGui::Text("%s via '%s'", nodes[e.from].label.c_str(), e.predicate.c_str());
                    first = false;
                }
            }
            if (first) ImGui::Text(" (None)");
        } else ImGui::Text("No node selected (left-click to select / drag).");
        ImGui::Separator();
        ImGui::Text("Pan offset: (%.1f, %.1f) (left-drag empty / right-drag / two-finger trackpad)", pan_offset.x, pan_offset.y);
        ImGui::EndChild();
        ImGui::EndChild();

        ImGui::SameLine();
        ImGui::BeginChild("SummaryWidget", ImVec2(summary_width, canvas_size.y), true);

        ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, ImVec2(0, 5));
        // Removed custom font loading, so this block is also removed
        // if (large_font) {
        //     ImGui::PushFont(large_font);
        // }
        ImGui::Text("Graph Summary");
        // if (large_font) {
        //     ImGui::PopFont();
        // }
        ImGui::PopStyleVar();

        ImGui::Text("------------------");
        ImGui::Text("Number of Nodes: %lu", nodes.size());
        ImGui::Text("Number of Edges: %lu", edges.size());
        ImGui::Text("------------------");

        if (selected_node >= 0 && selected_node < nodes.size()) {
            ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, ImVec2(0, 5));
            // Removed custom font loading
            // if (large_font) {
            //     ImGui::PushFont(large_font);
            // }
            ImGui::Text("Link Prediction for '%s'", nodes[selected_node].label.c_str());
            // if (large_font) {
            //     ImGui::PopFont();
            // }
            ImGui::PopStyleVar();
            ImGui::Separator();
            
            std::vector<std::pair<int, float>> predictions = predictLinksForNode(selected_node);
            if (predictions.empty()) {
                ImGui::Text("No potential links found.");
            } else {
                if (ImGui::BeginTable("predictions_table", 3, ImGuiTableFlags_Borders | ImGuiTableFlags_Resizable)) {
                    ImGui::TableSetupColumn("Predicted Node");
                    ImGui::TableSetupColumn("Score");
                    ImGui::TableSetupColumn("Relation");
                    ImGui::TableHeadersRow();

                    for (const auto& pred : predictions) {
                        ImGui::TableNextRow();
                        
                        ImGui::TableNextColumn();
                        ImGui::TextUnformatted(nodes[pred.first].label.c_str());
                        
                        ImGui::TableNextColumn();
                        ImGui::Text("%.2f", pred.second);

                        ImGui::TableNextColumn();
                        ImGui::TextUnformatted(getConceptualMeaning(pred.second).c_str());
                    }
                    ImGui::EndTable();
                }
            }
        }
        
        ImGui::Separator();
        
        ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, ImVec2(0, 5));
        // Removed custom font loading
        // if (large_font) {
        //     ImGui::PushFont(large_font);
        // }
        ImGui::Text("Page Rank");
        // if (large_font) {
        //     ImGui::PopFont();
        // }
        ImGui::PopStyleVar();
        ImGui::Separator();
        
        if (page_rank_scores.empty()) {
            ImGui::Text("No data to calculate Page Rank.");
        } else {
            if (ImGui::BeginTable("pagerank_table", 3, ImGuiTableFlags_Borders | ImGuiTableFlags_Resizable)) {
                ImGui::TableSetupColumn("Node");
                ImGui::TableSetupColumn("Score");
                ImGui::TableSetupColumn("Connectivity");
                ImGui::TableHeadersRow();

                for (const auto& rank_pair : page_rank_scores) {
                    ImGui::TableNextRow();
                    
                    ImGui::TableNextColumn();
                    ImGui::TextUnformatted(nodes[rank_pair.first].label.c_str());
                    
                    ImGui::TableNextColumn();
                    ImGui::Text("%.5f", rank_pair.second);
                    
                    ImGui::TableNextColumn();
                    ImGui::TextUnformatted(getPageRankMeaning(rank_pair.second).c_str());
                }
                ImGui::EndTable();
            }
        }
        
        ImGui::EndChild();
        ImGui::End();
    }
};

std::vector<Triple> LoadTriplesFromCSV(const std::string& filename) {
    std::vector<Triple> triples;
    std::ifstream file(filename);

    if (!file.is_open()) {
        std::cerr << "Error: Could not open file " << filename << std::endl;
        return triples;
    }

    std::string line;
    std::getline(file, line);

    while (std::getline(file, line)) {
        std::stringstream ss(line);
        std::string node_name, edge_name, name_of_component, severity;

        if (std::getline(ss, node_name, ',') &&
            std::getline(ss, edge_name, ',') &&
            std::getline(ss, name_of_component, ',') &&
            std::getline(ss, severity))
        {
            if (!severity.empty() && severity.back() == '\r') {
                severity.pop_back();
            }
            triples.push_back({node_name, edge_name, name_of_component, severity});
        }
    }

    file.close();
    std::cout << "Successfully loaded " << triples.size() << " triples from " << filename << std::endl;
    return triples;
}

int main() {
    if (!glfwInit()) return -1;
    GLFWwindow* window = glfwCreateWindow(1200, 800, "Semantic Graph Visualizer", NULL, NULL);
    if (!window) {
        glfwTerminate();
        return -1;
    }
    glfwMakeContextCurrent(window);
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO(); (void)io;
    io.Fonts->AddFontDefault();

    // The custom font loading line is removed
    ImFont* large_font = nullptr;
    
    // The conditional check for a nullptr font is not needed,
    // as the program will now use the default font.
    
    ImGui::StyleColorsLight();
    ImGui_ImplGlfw_InitForOpenGL(window, true);
    ImGui_ImplOpenGL3_Init("#version 110");
    
    GraphVisualizer graph;
    graph.setLargeFont(large_font);

    std::string filename = "graph_data.csv";
    std::vector<Triple> triples_from_file = LoadTriplesFromCSV(filename);

    if (triples_from_file.empty()) {
        std::cerr << "Warning: No data to visualize. The CSV file might be empty or missing." << std::endl;
    } else {
        graph.LoadTriples(triples_from_file);
        graph.calculatePageRank();
    }

    while (!glfwWindowShouldClose(window)) {
        glfwPollEvents();
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();
        graph.UpdatePhysics();
        graph.Render();
        ImGui::Render();
        int display_w, display_h;
        glfwGetFramebufferSize(window, &display_w, &display_h);
        glViewport(0, 0, display_w, display_h);
        glClearColor(1.0f, 1.0f, 1.0f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        glfwSwapBuffers(window);
    }
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();
    glfwDestroyWindow(window);
    glfwTerminate();
    return 0;
}