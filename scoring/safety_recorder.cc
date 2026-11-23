#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <map>
#include <set>
#include <string>

#include <gazebo/common/Events.hh>
#include <gazebo/common/Mesh.hh>
#include <gazebo/common/MeshManager.hh>
#include <gazebo/gazebo.hh>
#include <gazebo/physics/physics.hh>

namespace gazebo
{
class ArenaSafetyRecorder : public WorldPlugin
{
  public: void Load(physics::WorldPtr world, sdf::ElementPtr) override
  {
    const char *output = std::getenv("ARENA_SAFETY_DIR");
    if (!output)
      gzthrow("ARENA_SAFETY_DIR is required");
    this->world = world;
    const std::string directory(output);
    this->records.open(directory + "/safety.tsv");
    this->meshOutput.open(directory + "/static-geometry.tsv");
    if (!this->records || !this->meshOutput)
      gzthrow("Cannot open Arena safety recording");
    this->records << std::setprecision(12);
    this->meshOutput << std::setprecision(12);
    this->contacts = world->Physics()->GetContactManager();
    this->contacts->SetNeverDropContacts(true);
    this->update = event::Events::ConnectWorldUpdateEnd([this]() { this->Sample(); });
  }

  private: void WriteMesh(const physics::ModelPtr &model)
  {
    for (const auto &link : model->GetLinks())
    {
      for (const auto &collision : link->GetCollisions())
      {
        auto shape = boost::dynamic_pointer_cast<physics::MeshShape>(collision->GetShape());
        if (!shape)
          continue;
        const auto *mesh = common::MeshManager::Instance()->Load(shape->GetMeshURI());
        if (!mesh)
          gzthrow("Cannot read map collision mesh");
        const auto pose = collision->WorldPose();
        for (unsigned int part = 0; part < mesh->GetSubMeshCount(); ++part)
        {
          const auto *section = mesh->GetSubMesh(part);
          for (unsigned int i = 0; i + 2 < section->GetIndexCount(); i += 3)
          {
            for (unsigned int vertex = 0; vertex < 3; ++vertex)
            {
              auto local = section->Vertex(section->GetIndex(i + vertex));
              local *= shape->Scale();
              const auto point = pose.Pos() + pose.Rot().RotateVector(local);
              this->meshOutput << (vertex ? "\t" : "") << point.X() << '\t' << point.Y();
            }
            this->meshOutput << '\n';
          }
        }
      }
    }
    this->meshOutput.close();
  }

  private: void WriteRobotContacts(double now)
  {
    std::set<std::string> touching;
    const auto &records = this->contacts->GetContacts();
    for (unsigned int i = 0; i < this->contacts->GetContactCount(); ++i)
    {
      const auto *contact = records[i];
      if (!contact->count || !contact->collision1 || !contact->collision2)
        continue;
      const auto first = contact->collision1->GetLink()->GetModel()->GetName();
      const auto second = contact->collision2->GetLink()->GetModel()->GetName();
      if (first == "turtlebot3")
        touching.insert(second);
      if (second == "turtlebot3")
        touching.insert(first);
    }
    touching.erase("ground_plane");
    touching.erase("turtlebot3");
    for (const auto &name : touching)
    {
      const auto previous = this->lastContact.find(name);
      if (previous == this->lastContact.end() || now - previous->second >= 0.1)
        this->records << "contact\t" << now << '\t' << name << '\n';
      this->lastContact[name] = now;
    }
  }

  private: void WriteBody(double now, const physics::ModelPtr &model)
  {
    for (const auto &link : model->GetLinks())
    {
      for (const auto &collision : link->GetCollisions())
      {
        const auto shape = collision->GetShape();
        const auto pose = collision->WorldPose();
        const auto box = boost::dynamic_pointer_cast<physics::BoxShape>(shape);
        const auto cylinder = boost::dynamic_pointer_cast<physics::CylinderShape>(shape);
        if (!box && !cylinder)
          continue;
        this->records << "shape\t" << now << '\t' << model->GetName();
        auto writePoint = [&](double x, double y, double z)
        {
          const auto p = pose.Pos() + pose.Rot().RotateVector({x, y, z});
          this->records << '\t' << p.X() << '\t' << p.Y();
        };
        if (box)
        {
          const auto size = box->Size() / 2;
          for (int x : {-1, 1})
            for (int y : {-1, 1})
              for (int z : {-1, 1})
                writePoint(x * size.X(), y * size.Y(), z * size.Z());
        }
        else
        {
          for (int i = 0; i < 24; ++i)
          {
            const double angle = i * 2 * std::acos(-1.0) / 24;
            for (int z : {-1, 1})
              writePoint(cylinder->GetRadius() * std::cos(angle),
                         cylinder->GetRadius() * std::sin(angle), z * cylinder->GetLength() / 2);
          }
        }
        this->records << '\n';
      }
    }
  }

  private: void Sample()
  {
    const double now = this->world->SimTime().Double();
    this->WriteRobotContacts(now);
    if (now < this->nextSample)
      return;
    const auto robot = this->world->ModelByName("turtlebot3");
    const auto map = this->world->ModelByName("my_mesh");
    if (!robot || !map)
      return;
    if (this->meshOutput.is_open())
      this->WriteMesh(map);
    this->nextSample = now + 0.05;
    for (const auto &model : this->world->Models())
    {
      if (model == robot || model->GetName().compare(0, 7, "person_") == 0)
        this->WriteBody(now, model);
    }
    this->records.flush();
  }

  private: physics::WorldPtr world;
  private: physics::ContactManager *contacts = nullptr;
  private: event::ConnectionPtr update;
  private: std::ofstream records;
  private: std::ofstream meshOutput;
  private: std::map<std::string, double> lastContact;
  private: double nextSample = 0;
};
GZ_REGISTER_WORLD_PLUGIN(ArenaSafetyRecorder)
}
