<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import StatusBadge from "../components/StatusBadge.vue";
import StatGrid from "../components/StatGrid.vue";
import { parkingApi } from "../api/parking";

const spaces = ref([]);
const stats = ref({});
const loading = ref(false);
const error = ref("");

const anomalies = ref([]);
const pendingCount = ref(0);
const anomalyMessage = ref("");
const showAnomalyForm = ref(false);
const showResolveModal = ref(false);
const resolvingAnomaly = ref(null);
const resolveForm = reactive({ result: "", status: "resolved" });
const form = reactive({
  space_code: "",
  plate_number: "",
  description: "",
});

const statItems = computed(() => [
  { label: "总车位", value: spaces.value.length },
  { label: "空闲", value: stats.value.free || 0 },
  { label: "占用", value: stats.value.occupied || 0 },
  { label: "预约", value: stats.value.reserved || 0 },
  { label: "维护", value: stats.value.maintenance || 0 },
  { label: "待处理异常", value: pendingCount.value },
]);

async function loadSpaces() {
  loading.value = true;
  error.value = "";
  try {
    const data = await parkingApi.getSpaces();
    spaces.value = data.items;
    stats.value = data.stats;
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

async function loadAnomalies() {
  try {
    const data = await parkingApi.getAnomalies({ status: "pending" });
    anomalies.value = data.items;
    pendingCount.value = data.pending_count;
  } catch {
    pendingCount.value = 0;
  }
}

async function updateStatus(space, status) {
  const plate = status === "occupied" ? space.plate_number || "临A00001" : null;
  await parkingApi.updateSpace(space.id, { status, plate_number: plate });
  await loadSpaces();
}

function openAnomalyForm(spaceCode, plateNumber) {
  form.space_code = spaceCode;
  form.plate_number = plateNumber || "";
  form.description = "";
  anomalyMessage.value = "";
  showAnomalyForm.value = true;
}

async function submitAnomaly() {
  anomalyMessage.value = "";
  try {
    await parkingApi.createAnomaly(form);
    showAnomalyForm.value = false;
    await loadAnomalies();
  } catch (err) {
    anomalyMessage.value = err.message;
  }
}

function openResolveModal(anomaly) {
  resolvingAnomaly.value = anomaly;
  resolveForm.result = "";
  resolveForm.status = "resolved";
  showResolveModal.value = true;
}

async function submitResolve() {
  if (!resolvingAnomaly.value) return;
  try {
    await parkingApi.resolveAnomaly(resolvingAnomaly.value.id, {
      result: resolveForm.result,
      status: resolveForm.status,
    });
    showResolveModal.value = false;
    resolvingAnomaly.value = null;
    await loadAnomalies();
  } catch {
    anomalyMessage.value = "处理失败";
  }
}

onMounted(() => {
  loadSpaces();
  loadAnomalies();
});
</script>

<template>
  <div class="page-stack">
    <header class="page-header">
      <div>
        <h2>车位状态监控</h2>
        <p>实时查看车位占用、预约和维护状态，上报异常占位。</p>
      </div>
      <div style="display: flex; gap: 10px;">
        <button class="secondary-button" type="button" @click="loadAnomalies">刷新异常</button>
        <button class="primary-button" type="button" @click="loadSpaces">刷新车位</button>
      </div>
    </header>

    <StatGrid :stats="statItems" />
    <p v-if="error" class="error-text">{{ error }}</p>

    <section v-if="anomalies.length > 0 || pendingCount > 0" class="table-section">
      <h3>待处理异常</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>车位</th>
              <th>车牌</th>
              <th>说明</th>
              <th>上报时间</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in anomalies" :key="a.id">
              <td>{{ a.space_code }}</td>
              <td>{{ a.plate_number || "—" }}</td>
              <td>{{ a.description }}</td>
              <td>{{ a.created_at }}</td>
              <td><StatusBadge :status="a.status" /></td>
              <td><button class="small-button" type="button" @click="openResolveModal(a)">处理</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div class="space-grid" :class="{ muted: loading }">
      <article v-for="space in spaces" :key="space.id" class="space-card">
        <div>
          <strong>{{ space.code }}</strong>
          <span>{{ space.area }}</span>
        </div>
        <StatusBadge :status="space.status" />
        <p>{{ space.plate_number || "无绑定车辆" }}</p>
        <select :value="space.status" @change="updateStatus(space, $event.target.value)">
          <option value="free">空闲</option>
          <option value="occupied">占用</option>
          <option value="reserved">预约</option>
          <option value="maintenance">维护</option>
        </select>
        <button class="small-button" type="button" @click="openAnomalyForm(space.code, space.plate_number)">上报异常</button>
      </article>
    </div>

    <div v-if="showAnomalyForm" class="modal-overlay" @click.self="showAnomalyForm = false">
      <div class="modal-panel">
        <h3>上报异常占位</h3>
        <form class="form-panel" @submit.prevent="submitAnomaly">
          <label>车位编号<input v-model="form.space_code" required /></label>
          <label>车牌号<input v-model="form.plate_number" placeholder="可选" /></label>
          <label>异常说明<input v-model="form.description" required placeholder="如：车辆长期未动、占位不停车等" /></label>
          <div style="display:flex;gap:10px;">
            <button class="primary-button" type="submit" style="flex:1;">提交</button>
            <button class="secondary-button" type="button" style="flex:1;" @click="showAnomalyForm = false">取消</button>
          </div>
          <p v-if="anomalyMessage" class="error-text">{{ anomalyMessage }}</p>
        </form>
      </div>
    </div>

    <div v-if="showResolveModal" class="modal-overlay" @click.self="showResolveModal = false">
      <div class="modal-panel">
        <h3>处理异常</h3>
        <form class="form-panel" @submit.prevent="submitResolve">
          <label>处理结果<input v-model="resolveForm.result" required placeholder="如：已通知车主移车" /></label>
          <label>处理状态
            <select v-model="resolveForm.status">
              <option value="resolved">已处理</option>
              <option value="dismissed">已忽略</option>
            </select>
          </label>
          <div style="display:flex;gap:10px;">
            <button class="primary-button" type="submit" style="flex:1;">确认</button>
            <button class="secondary-button" type="button" style="flex:1;" @click="showResolveModal = false">取消</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
