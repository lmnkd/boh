// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.17;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/structs/EnumerableSet.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

contract HealthDataValidator is AccessControl, ReentrancyGuard {

    using EnumerableSet for EnumerableSet.AddressSet;

    // RUOLI
    bytes32 public constant DOCTOR_ROLE = keccak256("DOCTOR_ROLE");
    bytes32 public constant VALIDATOR_ROLE = keccak256("VALIDATOR_ROLE");
    bytes32 public constant AUTHORITY_ROLE = keccak256("AUTHORITY_ROLE");
    bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");
    bytes32 public constant PATIENT_ROLE = keccak256("PATIENT_ROLE");

    enum Status { PENDING, APPROVED, REJECTED }

    struct Visit {
        address doctor;
        address patient;
        bytes32 patientId;
        bytes32 dataHash;
        bool confirmed;
    }

    struct Record {
        uint256 visitId;
        address authority;
        bytes32 patientId;
        bytes32 dataHash;
        Status status;
        uint256 approveVotes;
        uint256 rejectVotes;
        mapping(address => bool) voted;
    }

    struct Probability {
        uint256 recordId;
        uint256 prior;
        uint256 posterior;
        uint256 updatedAt;
    }

    // STORAGE
    EnumerableSet.AddressSet private validators;

    uint256 public visitCount;
    uint256 public recordCount;
    uint256 public probabilityCount;

    mapping(uint256 => Visit) private visits;
    mapping(uint256 => Record) private records;
    mapping(uint256 => Probability) private probabilities;
    mapping(uint256 => bool) public visitHasRecord;

    // EVENTI
    event VisitSubmitted(uint256 visitId, address doctor, address patient);
    event VisitConfirmed(uint256 visitId, address patient);
    event RecordProposed(uint256 recordId, uint256 visitId);
    event VoteCast(uint256 recordId, address voter, bool approve);
    event RecordFinalized(uint256 recordId, Status status);
    event ProbabilityUpdated(uint256 probId, uint256 recordId);

    // COSTRUTTORE
    constructor(address[] memory initialValidators) {
    _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);

    // evita possibili problemi con array vuoti o Quorum
    if (initialValidators.length == 0) {
        validators.add(msg.sender);
        _grantRole(VALIDATOR_ROLE, msg.sender);
        return;
    }

    for (uint i = 0; i < initialValidators.length; i++) {
        validators.add(initialValidators[i]);
        _grantRole(VALIDATOR_ROLE, initialValidators[i]);
    }
}

    // ======================
    // ROLE MANAGEMENT
    // ======================

    function addDoctor(address a) external onlyRole(DEFAULT_ADMIN_ROLE) {
        grantRole(DOCTOR_ROLE, a);
    }

    function addAuthority(address a) external onlyRole(DEFAULT_ADMIN_ROLE) {
        grantRole(AUTHORITY_ROLE, a);
    }

    function addOracle(address a) external onlyRole(DEFAULT_ADMIN_ROLE) {
        grantRole(ORACLE_ROLE, a);
    }

    function addPatient(address a) external onlyRole(DEFAULT_ADMIN_ROLE) {
        grantRole(PATIENT_ROLE, a);
    }

    function addValidator(address a) external onlyRole(DEFAULT_ADMIN_ROLE) {
        validators.add(a);
        grantRole(VALIDATOR_ROLE, a);
    }

    function removeValidator(address a) external onlyRole(DEFAULT_ADMIN_ROLE) {
        validators.remove(a);
        revokeRole(VALIDATOR_ROLE, a);
    }

    function getValidators() external view returns (address[] memory) {
        return validators.values();
    }

    // ======================
    // STEP 1: SUBMIT VISIT
    // ======================

    function submitVisit(
        address patient,
        bytes32 patientId,
        bytes32 dataHash
    ) external returns (uint256 visitId) {

        visitId = ++visitCount;

        visits[visitId] = Visit({
            doctor: msg.sender,
            patient: patient,
            patientId: patientId,
            dataHash: dataHash,
            confirmed: false
        });

        emit VisitSubmitted(visitId, msg.sender, patient);
    }

    // ======================
    // STEP 2: CONFIRM VISIT
    // ======================

    function confirmVisit(uint256 visitId) external {
        require(visitId > 0 && visitId <= visitCount, "Invalid visit");

        Visit storage v = visits[visitId];

        require(msg.sender == v.patient, "Not patient");
        require(!v.confirmed, "Already confirmed");

        v.confirmed = true;

        emit VisitConfirmed(visitId, msg.sender);
    }

    // ======================
    // STEP 3: PROPOSE RECORD
    // ======================

    function proposeRecord(uint256 visitId, bytes32 dataHash)
        external
        onlyRole(AUTHORITY_ROLE)
        returns (uint256 recordId)
    {
        require(visitId > 0 && visitId <= visitCount, "Invalid visit");

        Visit storage v = visits[visitId];

        require(v.confirmed, "Visit not confirmed");
        require(!visitHasRecord[visitId], "Record exists");

        // 🔒 blocco manipolazione dati
        require(dataHash == v.dataHash, "Data mismatch");

        recordId = ++recordCount;

        Record storage r = records[recordId];
        r.visitId = visitId;
        r.authority = msg.sender;
        r.patientId = v.patientId;
        r.dataHash = dataHash;
        r.status = Status.PENDING;

        visitHasRecord[visitId] = true;

        emit RecordProposed(recordId, visitId);
    }

    // ======================
    // STEP 4: VOTING
    // ======================

    function vote(uint256 recordId, bool approve)
        external
        onlyRole(VALIDATOR_ROLE)
        nonReentrant
    {
        require(recordId > 0 && recordId <= recordCount, "Invalid record");

        Record storage r = records[recordId];

        require(!r.voted[msg.sender], "Already voted");
        require(r.status == Status.PENDING, "Finalized");

        r.voted[msg.sender] = true;

        if (approve) r.approveVotes++;
        else r.rejectVotes++;

        uint256 majority = validators.length() / 2 + 1;

        if (r.approveVotes >= majority) {
            r.status = Status.APPROVED;
            emit RecordFinalized(recordId, Status.APPROVED);
        } else if (r.rejectVotes >= majority) {
            r.status = Status.REJECTED;
            emit RecordFinalized(recordId, Status.REJECTED);
        }

        emit VoteCast(recordId, msg.sender, approve);
    }

    // ======================
    // STEP 5: ORACLE UPDATE
    // ======================

    function updateProbability(
        uint256 recordId,
        uint256 prior,
        uint256 posterior
    )
        external
        onlyRole(ORACLE_ROLE)
        returns (uint256 probId)
    {
        require(recordId > 0 && recordId <= recordCount, "Invalid record");
        require(records[recordId].status == Status.APPROVED, "Not approved");

        probId = ++probabilityCount;

        probabilities[probId] = Probability(
            recordId,
            prior,
            posterior,
            block.timestamp
        );

        emit ProbabilityUpdated(probId, recordId);
    }

    // ======================
    // GETTERS
    // ======================

    function getVisit(uint256 id) external view returns (Visit memory) {
        require(id > 0 && id <= visitCount, "Invalid visit");
        return visits[id];
    }

    function getRecord(uint256 id)
        external
        view
        returns (
            uint256 visitId,
            address authority,
            bytes32 patientId,
            bytes32 dataHash,
            Status status,
            uint256 approveVotes,
            uint256 rejectVotes
        )
    {
        require(id > 0 && id <= recordCount, "Invalid record");

        Record storage r = records[id];

        return (
            r.visitId,
            r.authority,
            r.patientId,
            r.dataHash,
            r.status,
            r.approveVotes,
            r.rejectVotes
        );
    }

    function hasVoted(uint256 recordId, address user)
        external
        view
        returns (bool)
    {
        return records[recordId].voted[user];
    }

    function getProbability(uint256 id)
        external
        view
        returns (Probability memory)
    {
        require(id > 0 && id <= probabilityCount, "Invalid prob");
        return probabilities[id];
    }
}